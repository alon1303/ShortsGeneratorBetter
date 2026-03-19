"""
Reddit Image Generator for creating visual hooks using Playwright and Jinja2.
Generates high-quality Reddit post overlays for video intros with transparent backgrounds.
Uses Jinja2 templates and Playwright for pixel-perfect rendering.
"""

import logging
import tempfile
import re
import asyncio
import math
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
    
    # viral/emotional words to highlight automatically
    POWER_KEYWORDS = {
        'AITA', 'ASSHOLE', 'MOM', 'BROTHER', 'SAVINGS', 'REFUSING', 'DEMANDED', 
        'TOOK', 'LEFT', 'MONEY', 'HOUSE', 'WIFE', 'UPDATE', 'ILLEGAL', 'CAUGHT'
    }

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
    
    def _apply_highlights(self, text: str) -> str:
        """
        Apply red highlights to dramatic words in the text.
        Highlights ALL CAPS words (2+ letters) and POWER_KEYWORDS (case-insensitive).
        Handles punctuation and possessives correctly.
        """
        if not text:
            return text
            
        words = text.split()
        highlighted_words = []
        
        for word in words:
            # Strip punctuation for keyword checking (e.g., "MOM'S," -> "MOMS")
            clean_word = re.sub(r'[^\w]', '', word).upper()
            
            # Remove 'S from the end of clean_word for power keyword checking (e.g. "MOMS" -> "MOM")
            base_clean_word = clean_word
            if clean_word.endswith('S') and len(clean_word) > 1:
                # Check if it was originally something like MOM'S
                if "'S" in word.upper() or (word.upper().endswith('S') and clean_word[:-1] in self.POWER_KEYWORDS):
                    base_clean_word = clean_word[:-1]

            # Condition 1: Word is ALL CAPS (at least 2 letters in clean word)
            # We check the original word part before punctuation
            is_all_caps = False
            alpha_part = re.sub(r'[^A-Z]', '', word)
            if len(alpha_part) >= 2 and alpha_part == re.sub(r'[^a-zA-Z]', '', word):
                 is_all_caps = True

            # Condition 2: Word (or its base) is in POWER_KEYWORDS
            is_power_word = clean_word in self.POWER_KEYWORDS or base_clean_word in self.POWER_KEYWORDS
            
            if is_all_caps or is_power_word:
                # To preserve punctuation outside the span if possible, but simplest is to wrap the whole "word" token
                highlighted_words.append(f'<span class="highlight">{word}</span>')
            else:
                highlighted_words.append(word)
                
        return " ".join(highlighted_words)

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
            
            # Apply highlighting to the title
            highlighted_title = self._apply_highlights(title)
            
            # Load and encode profile picture to Base64
            avatar_base64 = ""
            profile_pic_path = self.template_dir / "channels_profile.jpg"
            if profile_pic_path.exists():
                try:
                    with open(profile_pic_path, "rb") as img_file:
                        avatar_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to encode profile picture to Base64: {e}")
            
            # Prepare template data
            template_data = {
                "title": highlighted_title,
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
                "avatar_base64": avatar_base64,
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
                card_element = await page.query_selector('.post-card')
                if not card_element:
                    logger.warning("Could not find .post-card element, capturing full page")
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
        self.pop_in_duration = 0.8  # seconds for scale animation (Slow Pop In)
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
        Generate FFmpeg filter_complex string for advanced slide-up and fade-in animation.
        This approach statically scales the image once and animates Y/Alpha,
        preventing overlay clipping bugs and making rendering 100x faster.
        """
        TARGET_W = 950
        # Make the animation slightly faster for a snappier feel
        ANIM_DURATION = self.pop_in_duration / 2  
        FADE_DURATION = 0.5
        
        # Calculate when to start the fade out
        fade_start = self.card_end_time - FADE_DURATION
        
        # 1. Statically scale the image once to 950px (fast) and add Alpha transitions
        # 2. Animate the 'y' parameter in the overlay filter to create a slide-up effect
        # Position at y=(H-h)/3 instead of center (H-h)/2
        filter_str = (
            f"[1:v]scale={TARGET_W}:-1,format=rgba,"
            f"fade=t=in:st={self.card_start_time:.3f}:d={ANIM_DURATION:.1f}:alpha=1,"
            f"fade=t=out:st={fade_start:.3f}:d={FADE_DURATION:.1f}:alpha=1[animated];"
            f"[0:v][animated]overlay=x=(W-w)/2:"
            f"y='min((H-h)/3 + 100 - 100*min(max(t-{self.card_start_time:.3f},0)/{ANIM_DURATION:.3f},1), (H-h)/3)':"
            f"enable='between(t,{self.card_start_time:.2f},{self.card_end_time:.2f})'"
        )
        
        logger.debug(
            f"Generated high-performance animation filter: "
            f"card_start={self.card_start_time:.2f}s, "
            f"card_end={self.card_end_time:.2f}s, "
            f"anim_duration={ANIM_DURATION}s, "
            f"target_width={TARGET_W}px"
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