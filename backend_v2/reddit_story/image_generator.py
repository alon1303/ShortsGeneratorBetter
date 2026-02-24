"""
Reddit Image Generator for creating visual hooks.
Generates light-mode Reddit post overlays for video intros.
Includes two implementations:
1. RedditTitleCardGenerator: Pillow-based with dynamic text wrapping (primary)
2. RedditImageGenerator: HTML2Image-based with web rendering (fallback)
"""

import logging
import tempfile
import re
from pathlib import Path
from typing import Optional, Tuple, List
import base64

# Configure logging
logger = logging.getLogger(__name__)

# Constants for Reddit title card
TITLE_CARD_WIDTH = 800
TITLE_CARD_HEIGHT = 400
TITLE_FONT_SIZE = 36
TITLE_FONT_COLOR = (34, 34, 34)  # Dark gray #222222
TITLE_BG_COLOR = (255, 255, 255)  # White #FFFFFF
TITLE_BORDER_COLOR = (237, 239, 241)  # Light gray #EDEFF1
TITLE_TEXT_PADDING = 30
MAX_TITLE_LINES = 4

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    logger.warning("Pillow not available. Install with: pip install Pillow")

try:
    from html2image import Html2Image
    HTML2IMAGE_AVAILABLE = True
except ImportError:
    logger.warning("html2image not available. Install with: pip install html2image")
    HTML2IMAGE_AVAILABLE = False


class RedditTitleCardGenerator:
    """Generates Reddit-style title cards with text wrapping using Pillow."""
    
    def __init__(
        self,
        template_path: Optional[Path] = None,
        font_path: Optional[Path] = None
    ):
        """
        Initialize title card generator.
        
        Args:
            template_path: Path to base template image (optional)
            font_path: Path to font file (optional, uses default if not provided)
        """
        if not HAS_PILLOW:
            raise ImportError("Pillow is required for RedditTitleCardGenerator. Install with: pip install Pillow")
        
        self.template_path = template_path
        self.font_path = font_path
        
        # Default font (will try to load system font if font_path not provided)
        self.title_font = None
        self.line_height = TITLE_FONT_SIZE + 10
        
        logger.info("RedditTitleCardGenerator initialized (Pillow-based)")
    
    def _load_font(self, font_size: int = TITLE_FONT_SIZE) -> Optional[ImageFont.FreeTypeFont]:
        """Load font with fallback."""
        try:
            if self.font_path and self.font_path.exists():
                font = ImageFont.truetype(str(self.font_path), font_size)
                logger.debug(f"Loaded font from {self.font_path}")
                return font
            else:
                # Try to load system font
                font = ImageFont.truetype("arial.ttf", font_size)
                logger.debug("Loaded system font 'arial.ttf'")
                return font
        except Exception as e:
            logger.warning(f"Could not load font: {e}")
            # Fall back to default font
            try:
                font = ImageFont.load_default()
                logger.debug("Loaded default font")
                return font
            except:
                return None
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        """
        Wrap text to fit within max_width.
        
        Args:
            text: Text to wrap
            font: PIL font object
            max_width: Maximum width in pixels
            
        Returns:
            List of text lines
        """
        if not text or not font:
            return [text] if text else []
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            # Test if adding this word would exceed max width
            test_line = ' '.join(current_line + [word])
            # Estimate text width (PIL's textsize is deprecated, use textbbox)
            try:
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            except:
                # Fallback estimation
                text_width = len(test_line) * (TITLE_FONT_SIZE // 2)
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                
                # If a single word is too long, split it
                if len(current_line) == 1:
                    test_word = current_line[0]
                    try:
                        bbox = font.getbbox(test_word)
                        word_width = bbox[2] - bbox[0]
                    except:
                        word_width = len(test_word) * (TITLE_FONT_SIZE // 2)
                    
                    if word_width > max_width:
                        # Word is too long, need to split by characters
                        chars = list(test_word)
                        split_lines = []
                        current_chars = []
                        
                        for char in chars:
                            current_chars.append(char)
                            test_chars = ''.join(current_chars)
                            try:
                                bbox = font.getbbox(test_chars)
                                char_width = bbox[2] - bbox[0]
                            except:
                                char_width = len(test_chars) * (TITLE_FONT_SIZE // 2)
                            
                            if char_width > max_width:
                                split_lines.append(''.join(current_chars[:-1]))
                                current_chars = [char]
                        
                        if current_chars:
                            split_lines.append(''.join(current_chars))
                        
                        if split_lines:
                            # Add first split line to current line
                            if lines and lines[-1] == ' '.join(current_line[:-1]):
                                lines[-1] += ' ' + split_lines[0]
                            else:
                                lines.append(split_lines[0])
                            # Add remaining splits as new lines
                            lines.extend(split_lines[1:])
                            current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Limit to maximum lines
        if len(lines) > MAX_TITLE_LINES:
            lines = lines[:MAX_TITLE_LINES]
            lines[-1] = lines[-1][:50] + "..." if len(lines[-1]) > 50 else lines[-1]
        
        return lines
    
    def generate_title_card(
        self,
        title: str,
        output_path: Path,
        subreddit: str = "r/AskReddit",
        upvotes: int = 1000,
        time_ago: str = "5 hours ago"
    ) -> bool:
        """
        Generate a Reddit-style title card image.
        
        Args:
            title: Reddit post title
            output_path: Path to save the generated image
            subreddit: Subreddit name
            upvotes: Number of upvotes
            time_ago: Time posted
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create a new image with Reddit light theme colors
            image = Image.new('RGBA', (TITLE_CARD_WIDTH, TITLE_CARD_HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # Draw Reddit card background
            card_rect = [
                10, 10,  # Top-left
                TITLE_CARD_WIDTH - 10, TITLE_CARD_HEIGHT - 10  # Bottom-right
            ]
            draw.rounded_rectangle(card_rect, radius=15, fill=TITLE_BG_COLOR, outline=TITLE_BORDER_COLOR, width=2)
            
            # Load fonts
            title_font = self._load_font(TITLE_FONT_SIZE)
            metadata_font = self._load_font(20)
            
            # Draw subreddit and metadata
            metadata_y = 30
            if metadata_font:
                # Subreddit in bold (simulated with larger font)
                subreddit_font = self._load_font(22)
                if subreddit_font:
                    draw.text((30, metadata_y), subreddit, font=subreddit_font, fill=(255, 69, 0))  # Reddit orange
                    bbox = subreddit_font.getbbox(subreddit)
                    subreddit_width = bbox[2] - bbox[0]
                    
                    # Upvotes and time
                    metadata_text = f"• {upvotes:,} upvotes • {time_ago}"
                    draw.text((30 + subreddit_width + 15, metadata_y), metadata_text, font=metadata_font, fill=(120, 124, 126))
            
            # Draw title with text wrapping
            title_x = 30
            title_y = 80
            max_text_width = TITLE_CARD_WIDTH - 60  # 30px padding on each side
            
            if title_font:
                lines = self._wrap_text(title, title_font, max_text_width)
                
                for i, line in enumerate(lines):
                    if title_y + (i * self.line_height) > TITLE_CARD_HEIGHT - 50:
                        break  # Don't go beyond card bottom
                    
                    draw.text(
                        (title_x, title_y + (i * self.line_height)),
                        line,
                        font=title_font,
                        fill=TITLE_FONT_COLOR
                    )
            
            # Draw Reddit vote arrows (simplified)
            vote_center_x = 50
            vote_center_y = TITLE_CARD_HEIGHT // 2
            
            # Upvote arrow (orange)
            draw.polygon([
                (vote_center_x, vote_center_y - 15),
                (vote_center_x - 10, vote_center_y),
                (vote_center_x + 10, vote_center_y)
            ], fill=(255, 69, 0))
            
            # Vote count
            if metadata_font:
                draw.text((vote_center_x - 10, vote_center_y + 15), str(upvotes), font=metadata_font, fill=(120, 124, 126))
            
            # Downvote arrow (gray)
            draw.polygon([
                (vote_center_x, vote_center_y + 35),
                (vote_center_x - 10, vote_center_y + 20),
                (vote_center_x + 10, vote_center_y + 20)
            ], fill=(135, 138, 140))
            
            # Save image
            image.save(output_path, 'PNG')
            logger.info(f"Title card generated: {output_path}")
            
            # Log image details
            logger.debug(f"Title: '{title[:50]}...'")
            logger.debug(f"Image size: {TITLE_CARD_WIDTH}x{TITLE_CARD_HEIGHT}")
            logger.debug(f"Lines: {len(lines) if 'lines' in locals() else 'N/A'}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate title card: {e}")
            return False


class RedditImageGenerator:
    """Generates Reddit post overlay images using html2image (legacy)."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize Reddit image generator.
        
        Args:
            output_dir: Directory to save generated images (defaults to temp directory)
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "reddit_overlays"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if HTML2IMAGE_AVAILABLE:
            # Initialize Html2Image with Chrome/Chromium
            self.hti = Html2Image(
                browser='chrome',
                output_path=str(self.output_dir),
                size=(1080, 400),  # Width matches Shorts width, height for post
            )
            logger.info(f"RedditImageGenerator initialized with output directory: {self.output_dir}")
        else:
            self.hti = None
            logger.warning("RedditImageGenerator initialized without html2image - will use fallback")
    
    def _generate_reddit_post_html(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        flair: Optional[str] = None
    ) -> str:
        """
        Generate HTML for a light-mode Reddit post.
        
        Args:
            title: Post title
            subreddit: Subreddit name
            score: Upvote count
            author: Post author (optional)
            flair: Post flair (optional)
            
        Returns:
            HTML string for the Reddit post
        """
        # Format score with K/M suffix if large
        def format_score(num: int) -> str:
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            elif num >= 1000:
                return f"{num/1000:.1f}K"
            return str(num)
        
        formatted_score = format_score(score)
        author_display = author or "Anonymous"
        
        # Reddit light mode colors
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    background: transparent;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .reddit-post {
                    background: #FFFFFF;
                    border: 1px solid #EDEFF1;
                    border-radius: 12px;
                    width: 1000px;
                    max-width: 90vw;
                    padding: 24px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                    position: relative;
                    overflow: hidden;
                }
                
                .post-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 16px;
                }
                
                .subreddit-icon {
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    margin-right: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                
                .subreddit-name {
                    color: #1C1C1C;
                    font-weight: 600;
                    font-size: 14px;
                }
                
                .post-meta {
                    color: #787C7E;
                    font-size: 12px;
                    margin-left: 8px;
                }
                
                .post-title {
                    color: #222222;
                    font-size: 28px;
                    font-weight: 600;
                    line-height: 1.3;
                    margin-bottom: 20px;
                    word-wrap: break-word;
                }
                
                .post-footer {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding-top: 16px;
                    border-top: 1px solid #EDEFF1;
                }
                
                .upvote-section {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .upvote-icon {
                    width: 24px;
                    height: 24px;
                    background: #FF4500;
                    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 4.5L7.5 9.5H10V14H14V9.5H16.5L12 4.5Z'/%3E%3C/svg%3E") no-repeat center;
                    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 4.5L7.5 9.5H10V14H14V9.5H16.5L12 4.5Z'/%3E%3C/svg%3E") no-repeat center;
                }
                
                .upvote-count {
                    color: #FF4500;
                    font-weight: 700;
                    font-size: 18px;
                }
                
                .author-section {
                    color: #787C7E;
                    font-size: 14px;
                }
                
                .flair {
                    display: inline-block;
                    background: #EDEFF1;
                    color: #1C1C1C;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 500;
                    margin-left: 12px;
                }
                
                @media (max-width: 600px) {
                    .post-title {
                        font-size: 22px;
                    }
                    
                    .reddit-post {
                        padding: 20px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="reddit-post">
                <div class="post-header">
                    <img class="subreddit-icon" src="https://www.redditstatic.com/desktop2x/img/favicon/apple-icon-57x57.png" alt="Reddit Logo">
                    <div>
                        <span class="subreddit-name">r/{subreddit}</span>
                        <span class="post-meta">• Posted by u/{author} • 5h ago</span>
                        {flair_html}
                    </div>
                </div>
                
                <h1 class="post-title">{title}</h1>
                
                <div class="post-footer">
                    <div class="upvote-section">
                        <div class="upvote-icon"></div>
                        <span class="upvote-count">{formatted_score}</span>
                    </div>
                    
                    <div class="author-section">
                        u/{author}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Add flair if provided
        flair_html = f'<span class="flair">{flair}</span>' if flair else ''
        
        # Fill template
        html = html_template.format(
            title=title,
            subreddit=subreddit,
            author=author_display,
            formatted_score=formatted_score,
            flair_html=flair_html
        )
        
        return html
    
    def generate_reddit_post_image(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        flair: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Generate a Reddit post overlay image.
        
        Args:
            title: Post title
            subreddit: Subreddit name
            score: Upvote count
            author: Post author (optional)
            flair: Post flair (optional)
            output_path: Optional output path for the image
            
        Returns:
            Path to generated PNG image, or None if failed
        """
        try:
            # Generate HTML
            html_content = self._generate_reddit_post_html(
                title=title,
                subreddit=subreddit,
                score=score,
                author=author,
                flair=flair
            )
            
            # Generate filename
            if output_path is None:
                import hashlib
                import time
                content_hash = hashlib.md5(f"{title}{subreddit}{score}".encode()).hexdigest()[:8]
                timestamp = int(time.time())
                filename = f"reddit_post_{content_hash}_{timestamp}.png"
                output_path = self.output_dir / filename
            
            if HTML2IMAGE_AVAILABLE and self.hti:
                # Use html2image to generate PNG
                logger.info(f"Generating Reddit post image: {title[:50]}...")
                
                # Save HTML to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                    f.write(html_content)
                    html_file = f.name
                
                try:
                    # Generate image
                    self.hti.screenshot(
                        html_file=html_file,
                        save_as=output_path.name,
                        size=(1080, 400)
                    )
                    
                    # Check if file was created
                    if output_path.exists():
                        logger.info(f"Reddit post image generated: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Failed to generate image: {output_path}")
                        return None
                        
                finally:
                    # Clean up HTML file
                    import os
                    if os.path.exists(html_file):
                        os.unlink(html_file)
                        
            else:
                # Fallback: Use Pillow-based generator if available
                if HAS_PILLOW:
                    logger.info("html2image not available, using Pillow-based generator instead")
                    pillow_generator = RedditTitleCardGenerator()
                    return pillow_generator.generate_title_card(
                        title=title,
                        output_path=output_path,
                        subreddit=subreddit,
                        upvotes=score,
                        time_ago="5 hours ago"
                    )
                else:
                    logger.warning("Neither html2image nor Pillow available, creating text file")
                    return self._generate_text_file_fallback(
                        title=title,
                        subreddit=subreddit,
                        score=score,
                        author=author,
                        output_path=output_path
                    )
                
        except Exception as e:
            logger.error(f"Failed to generate Reddit post image: {e}")
            return None
    
    def _generate_text_file_fallback(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Fallback method to generate a text file when no image generation is available.
        
        Args:
            title: Post title
            subreddit: Subreddit name
            score: Upvote count
            author: Post author (optional)
            output_path: Output path for the text file
            
        Returns:
            Path to generated text file
        """
        if output_path is None:
            output_path = self.output_dir / f"reddit_info_{hash(title) % 10000}.txt"
        
        text_content = f"""Reddit Post Info (Image generation failed)
========================================
Title: {title}
Subreddit: r/{subreddit}
Upvotes: {score}
Author: {author or 'Anonymous'}

Note: Install Pillow for proper image generation: pip install Pillow
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        logger.warning(f"Created text file instead of image: {output_path}")
        return output_path
    
    def cleanup_old_images(self, max_age_hours: int = 24) -> int:
        """
        Clean up old generated images.
        
        Args:
            max_age_hours: Maximum age of images in hours
            
        Returns:
            Number of files deleted
        """
        import time
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filepath in self.output_dir.glob("*.*"):
            try:
                file_age = current_time - filepath.stat().st_mtime
                
                if file_age > max_age_seconds:
                    filepath.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old image: {filepath}")
                    
            except Exception as e:
                logger.warning(f"Failed to delete image {filepath}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old Reddit post images")
        
        return deleted_count


class TitlePopupTimingCalculator:
    """Calculates timing for title popup animation and display."""
    
    def __init__(self, title_audio_duration: float, buffer_seconds: float = 0.2):
        """
        Initialize timing calculator.
        
        Args:
            title_audio_duration: Duration of title audio in seconds
            buffer_seconds: Additional buffer after audio ends (default: 0.2s)
        """
        self.title_audio_duration = title_audio_duration
        self.buffer_seconds = buffer_seconds
        
        # Animation parameters
        self.pop_in_duration = 0.2  # seconds for scale animation
        self.display_duration = title_audio_duration + buffer_seconds
        
        # Calculate key timing points
        self.card_start_time = 0.0
        self.card_full_visible_time = self.pop_in_duration
        self.card_end_time = self.card_start_time + self.display_duration
        self.subtitle_start_time = self.card_end_time  # Subtitles start after card disappears
        
        logger.info(
            f"Timing calculated: "
            f"Title audio: {title_audio_duration:.2f}s, "
            f"Display: {self.display_duration:.2f}s, "
            f"Card visible: {self.card_start_time:.2f}s to {self.card_end_time:.2f}s, "
            f"Subtitles start: {self.subtitle_start_time:.2f}s"
        )
    
    def get_ffmpeg_filter_for_animation(self, image_path: Path) -> str:
        """
        Generate FFmpeg filter for pop-in animation with scale from 0% to 80% over pop_in_duration.
        
        Args:
            image_path: Path to title card image
            
        Returns:
            FFmpeg filter_complex string for pop-in animation
        """
        # Pop-in animation: scale from 0% to 80% over pop_in_duration
        # Then remain at 80% scale until card_end_time
        # Add :eval=frame to allow time variable 't' evaluation
        filter_str = (
            f"[1:v]scale=w='if(between(t,{self.card_start_time},{self.card_full_visible_time}), "
            f"0.8*((t-{self.card_start_time})/{self.pop_in_duration})*iw, 0.8*iw)':"
            f"h='if(between(t,{self.card_start_time},{self.card_full_visible_time}), "
            f"0.8*((t-{self.card_start_time})/{self.pop_in_duration})*ih, 0.8*ih)':"
            f"force_original_aspect_ratio=decrease:eval=frame[overlay_scaled];"
            f"[0:v][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:"
            f"enable='between(t,{self.card_start_time},{self.card_end_time})'"
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


# Factory function for getting the appropriate generator
def get_title_card_generator(use_pillow: bool = True) -> RedditTitleCardGenerator:
    """
    Get a title card generator instance.
    
    Args:
        use_pillow: If True, use Pillow-based generator (recommended)
        
    Returns:
        RedditTitleCardGenerator instance
        
    Raises:
        ImportError: If Pillow is not installed and use_pillow=True
    """
    if use_pillow:
        if not HAS_PILLOW:
            raise ImportError("Pillow is required for title card generation. Install with: pip install Pillow")
        return RedditTitleCardGenerator()
    else:
        return RedditImageGenerator()


# Example usage
if __name__ == "__main__":
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Test Pillow-based generator
    if HAS_PILLOW:
        print("Testing Pillow-based RedditTitleCardGenerator...")
        pillow_generator = RedditTitleCardGenerator()
        
        test_output = Path(tempfile.gettempdir()) / "test_title_card.png"
        success = pillow_generator.generate_title_card(
            title="What's the most unexpectedly wholesome thing you've witnessed?",
            output_path=test_output,
            subreddit="r/AskReddit",
            upvotes=45200,
            time_ago="5 hours ago"
        )
        
        if success and test_output.exists():
            print(f"✅ Pillow title card generated: {test_output}")
            print(f"   File size: {test_output.stat().st_size} bytes")
            # Clean up
            test_output.unlink()
        else:
            print("❌ Failed to generate Pillow title card")
    else:
        print("❌ Pillow not available for testing")
    
    # Test html2image-based generator
    print("\nTesting html2image-based RedditImageGenerator...")
    html_generator = RedditImageGenerator()
    
    test_output2 = Path(tempfile.gettempdir()) / "test_html_image.png"
    result = html_generator.generate_reddit_post_image(
        title="Another test question for the community",
        subreddit="AskReddit",
        score=12500,
        author="TestUser123",
        flair="Serious",
        output_path=test_output2
    )
    
    if result and result.exists():
        print(f"✅ HTML image generated: {result}")
        print(f"   File size: {result.stat().st_size} bytes")
        # Clean up
        result.unlink()
    else:
        print("❌ HTML image generation failed or not available")
    
    # Test timing calculator
    print("\nTesting TitlePopupTimingCalculator...")
    timing_calc = TitlePopupTimingCalculator(title_audio_duration=3.5)
    timing_data = timing_calc.to_dict()
    print(f"Timing data: {timing_data}")
    
    print("\nAll tests completed!")


