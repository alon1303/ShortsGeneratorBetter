"""
Reddit Image Generator for creating visual hooks using Playwright and Jinja2.
Generates high-quality Reddit post overlays for video intros with transparent backgrounds.
Uses Jinja2 templates and Playwright for pixel-perfect rendering.
"""

import logging
import tempfile
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import base64
import hashlib
import time
import json

# Configure logging
logger = logging.getLogger(__name__)

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA2_AVAILABLE = True
except ImportError:
    logger.warning("jinja2 not available. Install with: pip install jinja2")
    JINJA2_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("playwright not available. Install with: pip install playwright")
    PLAYWRIGHT_AVAILABLE = False


class RedditImageGenerator:
    """Generates Reddit post overlay images using Playwright and Jinja2 templates."""
    
    def __init__(self, output_dir: Optional[Path] = None, template_dir: Optional[Path] = None):
        """
        Initialize Reddit image generator with Playwright and Jinja2.
        
        Args:
            output_dir: Directory to save generated images (defaults to temp directory)
            template_dir: Directory containing Jinja2 templates (defaults to project templates)
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "reddit_overlays"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup template directory
        if template_dir is None:
            template_dir = Path(__file__).parent.parent / "templates"
        self.template_dir = template_dir
        
        # Initialize Jinja2 environment
        self.jinja_env = None
        if JINJA2_AVAILABLE and self.template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
            logger.info(f"Jinja2 environment initialized with template directory: {self.template_dir}")
        else:
            logger.warning(f"Jinja2 not available or template directory not found: {self.template_dir}")
        
        # Playwright browser instance (initialized lazily)
        self._browser = None
        self._playwright = None
        self._playwright_context = None
        
        logger.info(f"RedditImageGenerator initialized with output directory: {self.output_dir}")
    
    async def _ensure_playwright_initialized(self):
        """Initialize Playwright browser if not already done."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not available. Install with: pip install playwright")
        
        if self._browser is None:
            self._playwright = await async_playwright().start()
            # Launch Chromium with transparent background support
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create browser context with transparent background
            self._playwright_context = await self._browser.new_context(
                viewport={'width': 1080, 'height': 1920},  # Shorts dimensions for proper scaling
                device_scale_factor=2.0,  # Retina/high DPI
            )
            logger.debug("Playwright browser initialized")
    
    async def _close_playwright(self):
        """Close Playwright browser if open."""
        if self._playwright_context:
            await self._playwright_context.close()
            self._playwright_context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.debug("Playwright browser closed")
    
    def _format_score(self, score: int) -> str:
        """Format score with K/M suffix if large."""
        if score >= 1000000:
            return f"{score/1000000:.1f}M"
        elif score >= 1000:
            return f"{score/1000:.1f}K"
        return str(score)
    
    def _format_comments(self, comments: int) -> str:
        """Format comment count with K/M suffix if large."""
        if comments >= 1000000:
            return f"{comments/1000000:.1f}M"
        elif comments >= 1000:
            return f"{comments/1000:.1f}K"
        return str(comments)
    
    def _get_time_ago(self) -> str:
        """Generate a realistic 'time ago' string."""
        # For simplicity, use fixed times
        import random
        times = ["5h ago", "3h ago", "8h ago", "1d ago", "2d ago", "1w ago"]
        return random.choice(times)
    
    def _render_template(self, template_data: Dict[str, Any]) -> str:
        """
        Render HTML template using Jinja2.
        
        Args:
            template_data: Dictionary with template variables
            
        Returns:
            Rendered HTML string
        """
        if not self.jinja_env:
            raise RuntimeError("Jinja2 environment not initialized")
        
        try:
            template = self.jinja_env.get_template("reddit_post.html")
            html = template.render(**template_data)
            return html
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            raise
    
    async def generate_reddit_post_image(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        flair: Optional[str] = None,
        comments: Optional[int] = None,
        theme_mode: str = "dark",  # "dark" or "light"
        body: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Generate a Reddit post overlay image with transparent background.
        
        Args:
            title: Post title
            subreddit: Subreddit name
            score: Upvote count
            author: Post author (optional)
            flair: Post flair (optional)
            comments: Comment count (optional)
            theme_mode: "dark" or "light" theme
            body: Post body text (optional)
            output_path: Optional output path for the image
            
        Returns:
            Path to generated PNG image with transparent background, or None if failed
        """
        try:
            # Validate inputs
            if not title or not subreddit:
                logger.error("Title and subreddit are required")
                return None
            
            author_display = author or "Anonymous"
            comments_display = comments or max(score // 10, 1)  # Estimate comments if not provided
            
            # Prepare template data
            template_data = {
                "title": title,
                "subreddit": subreddit,
                "author": author_display,
                "flair": flair,
                "score": score,
                "formatted_score": self._format_score(score),
                "comments": comments_display,
                "formatted_comments": self._format_comments(comments_display),
                "time_ago": self._get_time_ago(),
                "theme_mode": theme_mode,
                "body": body,
            }
            
            # Render HTML template
            logger.info(f"Rendering Reddit post template: {title[:50]}...")
            html_content = self._render_template(template_data)
            
            # Generate output path if not provided
            if output_path is None:
                content_hash = hashlib.md5(f"{title}{subreddit}{score}{author}".encode()).hexdigest()[:8]
                timestamp = int(time.time())
                filename = f"reddit_post_{content_hash}_{timestamp}.png"
                output_path = self.output_dir / filename
            
            # Ensure Playwright is initialized
            await self._ensure_playwright_initialized()
            
            # Create a new page for screenshot
            page = await self._playwright_context.new_page()
            
            try:
                # Set HTML content directly (no network request)
                await page.set_content(html_content, wait_until="networkidle")
                
                # Wait for animations to complete
                await page.wait_for_timeout(300)  # Wait for CSS animations
                
                # Take screenshot with transparent background
                logger.info(f"Taking screenshot with transparent background: {output_path}")
                
                # Get the bounding box of the post card
                card_element = await page.query_selector('.reddit-post-card')
                if not card_element:
                    logger.warning("Could not find .reddit-post-card element, capturing full page")
                    await page.screenshot(
                        path=str(output_path),
                        type='png',
                        omit_background=True,  # Transparent background
                        full_page=False,  # Capture viewport only
                        animations='disabled'
                    )
                else:
                    # Capture only the card element with padding
                    box = await card_element.bounding_box()
                    if box:
                        # Add some padding around the card
                        padding = 20
                        clip = {
                            'x': box['x'] - padding,
                            'y': box['y'] - padding,
                            'width': box['width'] + (padding * 2),
                            'height': box['height'] + (padding * 2)
                        }
                        await page.screenshot(
                            path=str(output_path),
                            type='png',
                            omit_background=True,
                            clip=clip,
                            animations='disabled'
                        )
                    else:
                        await page.screenshot(
                            path=str(output_path),
                            type='png',
                            omit_background=True,
                            full_page=False,
                            animations='disabled'
                        )
                
                # Verify file was created
                if output_path.exists() and output_path.stat().st_size > 0:
                    logger.info(f"Reddit post image generated successfully: {output_path} (size: {output_path.stat().st_size} bytes)")
                    
                    # Optional: Verify transparency
                    try:
                        from PIL import Image
                        img = Image.open(output_path)
                        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                            logger.debug("Image has transparency channel")
                        else:
                            logger.warning("Image may not have transparency channel")
                        img.close()
                    except ImportError:
                        logger.debug("PIL not available for transparency verification")
                    
                    return output_path
                else:
                    logger.error(f"Failed to generate image: {output_path}")
                    return None
                    
            finally:
                await page.close()
                
        except Exception as e:
            logger.error(f"Failed to generate Reddit post image: {e}")
            return None
    
    def generate_reddit_post_image_sync(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        flair: Optional[str] = None,
        comments: Optional[int] = None,
        theme_mode: str = "dark",
        body: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Synchronous wrapper for generate_reddit_post_image.
        Handles both sync and async contexts safely.
        
        Args:
            Same as generate_reddit_post_image
            
        Returns:
            Path to generated PNG image, or None if failed
        """
        try:
            # Try to get the current event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create a new one
                return asyncio.run(
                    self.generate_reddit_post_image(
                        title=title,
                        subreddit=subreddit,
                        score=score,
                        author=author,
                        flair=flair,
                        comments=comments,
                        theme_mode=theme_mode,
                        body=body,
                        output_path=output_path
                    )
                )
            
            # Check if the loop is running
            if not loop.is_running():
                # Loop exists but is not running, use run_until_complete
                return loop.run_until_complete(
                    self.generate_reddit_post_image(
                        title=title,
                        subreddit=subreddit,
                        score=score,
                        author=author,
                        flair=flair,
                        comments=comments,
                        theme_mode=theme_mode,
                        body=body,
                        output_path=output_path
                    )
                )
            
            # Loop is running (we're in an async context)
            # We need to run in this loop but carefully
            future = asyncio.ensure_future(
                self.generate_reddit_post_image(
                    title=title,
                    subreddit=subreddit,
                    score=score,
                    author=author,
                    flair=flair,
                    comments=comments,
                    theme_mode=theme_mode,
                    body=body,
                    output_path=output_path
                )
            )
            
            # This will block until the future is complete
            # Note: This can cause deadlocks if not careful, but should work for our use case
            return loop.run_until_complete(future)
            
        except Exception as e:
            logger.error(f"Failed in synchronous wrapper: {e}")
            return None
    
    async def cleanup(self):
        """Clean up Playwright resources."""
        await self._close_playwright()
    
    def __del__(self):
        """Ensure Playwright resources are cleaned up."""
        try:
            # Try to run cleanup in async context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task to cleanup
                loop.create_task(self.cleanup())
            else:
                loop.run_until_complete(self.cleanup())
        except:
            # If anything fails, just log
            logger.debug("Failed to cleanup Playwright in destructor")


class TitlePopupTimingCalculator:
    """Calculates timing for title popup animation and display."""
    
    def __init__(self, title_audio_duration: float, buffer_seconds: float = 0.0):
        """
        Initialize timing calculator.
        
        Args:
            title_audio_duration: Duration of title audio in seconds
            buffer_seconds: Additional buffer after audio ends (default: 0.0s)
        """
        self.title_audio_duration = title_audio_duration
        self.buffer_seconds = buffer_seconds
        
        # Animation parameters
        self.pop_in_duration = 0.2  # seconds for scale animation
        self.display_duration = title_audio_duration  # Card disappears exactly when title audio ends
        
        # Calculate key timing points
        self.card_start_time = 0.0
        self.card_full_visible_time = self.pop_in_duration
        self.card_end_time = self.card_start_time + self.display_duration
        self.subtitle_start_time = self.card_end_time  # Subtitles start after card disappears (when story starts)
        
        logger.info(
            f"Timing calculated: "
            f"Title audio: {title_audio_duration:.2f}s, "
            f"Display: {self.display_duration:.2f}s, "
            f"Card visible: {self.card_start_time:.2f}s to {self.card_end_time:.2f}s, "
            f"Subtitles start: {self.subtitle_start_time:.2f}s"
        )
    
    def get_ffmpeg_filter_for_animation(self, image_path: Path) -> str:
        """
        Generate FFmpeg filter_complex string for pop-in animation with alpha preservation.
        
        Creates a scale animation that grows from 50px to 900px over pop_in_duration seconds,
        then stays at full size until card_end_time, then disappears.
        
        Args:
            image_path: Path to the overlay image (PNG with transparency)
            
        Returns:
            FFmpeg filter_complex string for dynamic pop-in animation
        """
        TARGET_W = 900
        MIN_W = 50  # Minimum width to avoid 0 height calculation
        
        # Calculate width: grow from MIN_W to TARGET_W over pop_in_duration seconds
        # Use max(0, t - card_start_time) to avoid negative time values
        # Use min(..., 1) to clamp growth factor between 0 and 1
        width_expr = f"max({MIN_W}, {TARGET_W} * min(max(0, t-{self.card_start_time})/{self.pop_in_duration}, 1))"
        
        # Height: use FFmpeg's native aspect ratio preservation
        # With -loop 1 and -framerate 30, the image has a continuous timeline
        # so h=-1 works correctly with eval=frame
        filter_str = (
            f"[1:v]scale=w='{width_expr}':h=-1:eval=frame[overlay_scaled];"
            f"[0:v][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:shortest=1:"
            f"enable='between(t,{self.card_start_time},{self.card_end_time})'"
        )
        
        logger.debug(
            f"Generated pop-in animation filter: "
            f"card_start={self.card_start_time:.2f}s, "
            f"card_end={self.card_end_time:.2f}s, "
            f"pop_in={self.pop_in_duration:.2f}s, "
            f"target_width={TARGET_W}px, "
            f"min_width={MIN_W}px"
        )
        
        return filter_str
    
    def to_dict(self) -> dict:
        """Return timing data as dictionary."""
        return {
            "title_audio_duration": self.title_audio_duration,
            "buffer_seconds": self.buffer_seconds,
            "pop_in_duration": self.pop_in_duration,
            "display_duration": self.display_duration,
            "card_start_time": self.card_start_time,
            "card_full_visible_time": self.card_full_visible_time,
            "card_end_time": self.card_end_time,
            "subtitle_start_time": self.subtitle_start_time,
        }


# Backward compatibility wrapper
class LegacyRedditImageGenerator:
    """Legacy wrapper for backward compatibility during transition."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.generator = RedditImageGenerator(output_dir)
    
    def generate_reddit_post_image(self, *args, **kwargs) -> Optional[Path]:
        """Legacy method that calls the new synchronous wrapper."""
        return self.generator.generate_reddit_post_image_sync(*args, **kwargs)


# Example usage and testing
async def test_generator():
    """Test the new image generator."""
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Playwright-based RedditImageGenerator...")
    
    # Create generator
    generator = RedditImageGenerator()
    
    # Test parameters
    test_output = Path(tempfile.gettempdir()) / "test_playwright_image.png"
    
    try:
        # Generate image
        print(f"Generating test image: {test_output}")
        result = await generator.generate_reddit_post_image(
            title="AITA for refusing to give my mom my savings after she demanded it?",
            subreddit="AmItheAsshole",
            score=12500,
            author="ThrowRA_SaveAccount",
            flair="SERIOUS",
            comments=850,
            theme_mode="dark",
            body="I (28F) have been saving up for a down payment on a house for the past 5 years...",
            output_path=test_output
        )
        
        if result and result.exists():
            print(f"✅ HTML image generated with Playwright: {result}")
            print(f"   File size: {result.stat().st_size} bytes")
            
            # Test transparency
            try:
                from PIL import Image
                img = Image.open(result)
                print(f"   Image mode: {img.mode}")
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    print("   ✅ Image has transparency channel")
                else:
                    print("   ⚠️ Image may not have transparency channel")
                img.close()
            except ImportError:
                print("   ℹ️ PIL not available for transparency check")
            
            # Clean up
            result.unlink()
            print("   Test file cleaned up")
        else:
            print("❌ HTML image generation failed")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await generator.cleanup()
        print("\nPlaywright browser cleaned up")
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    # Run async test
    asyncio.run(test_generator())