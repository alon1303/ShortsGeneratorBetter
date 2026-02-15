"""
Reddit Image Generator for creating visual hooks.
Generates dark-mode Reddit post overlays for video intros.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import base64

# Configure logging
logger = logging.getLogger(__name__)

try:
    from html2image import Html2Image
    HTML2IMAGE_AVAILABLE = True
except ImportError:
    logger.warning("html2image not available. Install with: pip install html2image")
    HTML2IMAGE_AVAILABLE = False

class RedditImageGenerator:
    """Generates Reddit post overlay images for video hooks."""
    
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
        Generate HTML for a dark-mode Reddit post.
        
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
        
        # Reddit dark mode colors
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
                    background: #1A1A1B;
                    border: 1px solid #343536;
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
                    background: linear-gradient(135deg, #FF4500, #FF8717);
                    border-radius: 50%;
                    margin-right: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                }
                
                .subreddit-name {
                    color: #D7DADC;
                    font-weight: 600;
                    font-size: 14px;
                }
                
                .post-meta {
                    color: #818384;
                    font-size: 12px;
                    margin-left: 8px;
                }
                
                .post-title {
                    color: #D7DADC;
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
                    border-top: 1px solid #343536;
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
                    color: #818384;
                    font-size: 14px;
                }
                
                .flair {
                    display: inline-block;
                    background: #343536;
                    color: #D7DADC;
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
                    <div class="subreddit-icon">r/</div>
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
                # Fallback: Create a simple placeholder image using PIL if available
                logger.warning("html2image not available, using fallback method")
                return self._generate_fallback_image(
                    title=title,
                    subreddit=subreddit,
                    score=score,
                    author=author,
                    output_path=output_path
                )
                
        except Exception as e:
            logger.error(f"Failed to generate Reddit post image: {e}")
            return None
    
    def _generate_fallback_image(
        self,
        title: str,
        subreddit: str,
        score: int,
        author: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Fallback method to generate image when html2image is not available.
        Uses PIL if available, otherwise creates a simple text file.
        
        Args:
            title: Post title
            subreddit: Subreddit name
            score: Upvote count
            author: Post author (optional)
            output_path: Output path for the image
            
        Returns:
            Path to generated image or text file
        """
        try:
            # Try to use PIL
            from PIL import Image, ImageDraw, ImageFont
            PIL_AVAILABLE = True
        except ImportError:
            PIL_AVAILABLE = False
            logger.warning("PIL not available, creating text file instead")
        
        if PIL_AVAILABLE:
            try:
                # Create image with PIL
                width, height = 1080, 400
                image = Image.new('RGBA', (width, height), (26, 26, 27, 255))  # Dark gray background
                draw = ImageDraw.Draw(image)
                
                # Try to load a font
                try:
                    font_large = ImageFont.truetype("arial.ttf", 32)
                    font_medium = ImageFont.truetype("arial.ttf", 24)
                    font_small = ImageFont.truetype("arial.ttf", 18)
                except:
                    # Fallback to default font
                    font_large = ImageFont.load_default()
                    font_medium = ImageFont.load_default()
                    font_small = ImageFont.load_default()
                
                # Draw subreddit
                subreddit_text = f"r/{subreddit}"
                draw.text((50, 50), subreddit_text, fill=(215, 218, 220, 255), font=font_medium)
                
                # Draw title (wrapped)
                title_lines = []
                words = title.split()
                current_line = ""
                
                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    # Simple line wrapping
                    if len(test_line) > 40:  # Approximate character limit
                        title_lines.append(current_line)
                        current_line = word
                    else:
                        current_line = test_line
                
                if current_line:
                    title_lines.append(current_line)
                
                # Draw title lines
                y_offset = 100
                for line in title_lines:
                    draw.text((50, y_offset), line, fill=(215, 218, 220, 255), font=font_large)
                    y_offset += 40
                
                # Draw upvote count
                upvote_text = f"▲ {score}"
                draw.text((50, height - 80), upvote_text, fill=(255, 69, 0, 255), font=font_medium)
                
                # Draw author
                author_text = f"u/{author or 'Anonymous'}"
                draw.text((width - 200, height - 80), author_text, fill=(129, 131, 132, 255), font=font_small)
                
                # Save image
                if output_path is None:
                    output_path = self.output_dir / f"reddit_fallback_{hash(title) % 10000}.png"
                
                image.save(output_path, 'PNG')
                logger.info(f"Fallback Reddit image generated with PIL: {output_path}")
                return output_path
                
            except Exception as e:
                logger.error(f"PIL image generation failed: {e}")
                # Continue to text file fallback
        
        # Ultimate fallback: Create a text file
        if output_path is None:
            output_path = self.output_dir / f"reddit_info_{hash(title) % 10000}.txt"
        
        text_content = f"""Reddit Post Info (Image generation failed)
========================================
Title: {title}
Subreddit: r/{subreddit}
Upvotes: {score}
Author: {author or 'Anonymous'}

Note: Install html2image or Pillow for proper image generation.
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
        
        for filepath in self.output_dir.glob("*.png"):
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


# Example usage
if __name__ == "__main__":
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Test the image generator
    generator = RedditImageGenerator()
    
    # Generate a test image
    test_image = generator.generate_reddit_post_image(
        title="What's the most unexpectedly wholesome thing you've witnessed?",
        subreddit="AskReddit",
        score=45200,
        author="CuriousCat42",
        flair="Serious"
    )
    
    if test_image:
        print(f"✅ Test image generated: {test_image}")
        print(f"   File exists: {test_image.exists()}")
        print(f"   File size: {test_image.stat().st_size} bytes")
    else:
        print("❌ Failed to generate test image")
        print("   Make sure html2image is installed: pip install html2image")
        print("   Or install Pillow for fallback: pip install Pillow")
    
    # Clean up
    deleted = generator.cleanup_old_images(max_age_hours=1)
    print(f"Cleaned up {deleted} old images")