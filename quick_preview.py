#!/usr/bin/env python3
"""
Quick Preview Tool for Reddit Title Card UI Testing
This script generates a 3-second visual preview to test HTML/CSS changes
without running the full video generation pipeline.
"""

import logging
import sys
import subprocess
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend_v2 to the Python path
backend_path = Path(__file__).parent / "backend_v2"
sys.path.insert(0, str(backend_path))

from reddit_story.image_generator_new import RedditImageGenerator


def generate_mock_title_card() -> Path:
    """Generate a title card image using mock Reddit post data.
    
    Returns:
        Path to the generated title card PNG image.
    """
    logger.info("Generating mock Reddit title card...")
    
    # Create image generator
    generator = RedditImageGenerator()
    
    # Mock data for testing
    mock_data = {
        "title": "AITA for refusing to give my mom my savings after she demanded it?",
        "subreddit": "AmItheAsshole",
        "score": 12500,
        "author": "ThrowRA_SaveAccount",
        "flair": "SERIOUS",
        "comments": 850,
        "theme_mode": "dark",
        "body": "I (28F) have been saving up for a down payment on a house for the past 5 years. My mom found out about my savings and demanded I give it to her to pay off her credit card debt. I refused, and now she's telling the whole family I'm selfish and ungrateful."
    }
    
    # Generate the image
    output_path = Path.cwd() / "title_card.png"
    
    logger.info(f"Using mock data: Title='{mock_data['title'][:50]}...'")
    logger.info(f"Output will be saved to: {output_path}")
    
    try:
        # Use synchronous wrapper for simplicity
        result_path = generator.generate_reddit_post_image_sync(
            title=mock_data["title"],
            subreddit=mock_data["subreddit"],
            score=mock_data["score"],
            author=mock_data["author"],
            flair=mock_data["flair"],
            comments=mock_data["comments"],
            theme_mode=mock_data["theme_mode"],
            body=mock_data["body"],
            output_path=output_path
        )
        
        if result_path and result_path.exists() and result_path.stat().st_size > 0:
            logger.info(f"✅ Title card generated successfully: {result_path}")
            logger.info(f"   File size: {result_path.stat().st_size} bytes")
            return result_path
        else:
            logger.error("❌ Failed to generate title card")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Error generating title card: {e}")
        sys.exit(1)


def create_3s_preview_video(title_card_path: Path) -> Path:
    """Create a 3-second preview video with title card overlay.
    
    Args:
        title_card_path: Path to the title card PNG image.
        
    Returns:
        Path to the generated preview video.
    """
    logger.info("Creating 3-second preview video...")
    
    # Check for background video
    background_path = Path.cwd() / "test_bg.mp4"
    if not background_path.exists():
        logger.error(f"❌ Background video not found: {background_path}")
        logger.info("Please place a background video named 'test_bg.mp4' in the root directory.")
        logger.info("You can use any 1080x1920 MP4 video as background.")
        sys.exit(1)
    
    # Output video path
    output_path = Path.cwd() / "preview_output.mp4"
    
    # FFmpeg command to create 3-second preview with overlay
    # Steps:
    # 1. Trim background to exactly 3 seconds
    # 2. Overlay title card at center for entire duration
    # 3. Output without audio
    
    # Build FFmpeg command as list of strings (best practice per .clinerules)
    # This mimics the real pipeline's TitlePopupTimingCalculator logic:
    # 1. Force background to exactly 1080x1920 canvas (crop if needed)
    # 2. Scale title card to exactly 80% of its original size (matching real pipeline's scaling formula)
    # 3. Center overlay on the canvas
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file without asking
        '-i', str(background_path),  # Background video input
        '-i', str(title_card_path),  # Title card image input
        '-filter_complex', (
            '[0:v]trim=duration=3,setpts=PTS-STARTPTS,'  # Trim background to 3 seconds
            'scale=1080:1920:force_original_aspect_ratio=increase,'  # Force to 1080x1920, crop if needed
            'crop=1080:1920[bg];'  # Ensure exact 1080x1920 canvas
            '[1:v]scale=w=0.8*iw:h=0.8*ih/sar:force_original_aspect_ratio=decrease[overlay_scaled];'  # Exact scaling from real pipeline (video_composer.py line 208)
            '[bg][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:enable=\'between(t,0,3)\'[v]'  # Center overlay
        ),
        '-map', '[v]',  # Map video output
        '-an',  # No audio
        '-t', '3',  # Ensure output is exactly 3 seconds
        '-s', '1080x1920',  # Explicitly set output resolution
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-movflags', '+faststart',
        str(output_path)
    ]
    
    logger.info(f"Running FFmpeg command to create preview: {output_path}")
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")
    
    try:
        # Execute FFmpeg command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True  # Raises CalledProcessError on non-zero exit
        )
        
        # Check if output was created
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"✅ Preview video created successfully: {output_path}")
            logger.info(f"   File size: {output_path.stat().st_size} bytes")
            return output_path
        else:
            logger.error("❌ Preview video file was not created")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg command failed with exit code {e.returncode}")
        logger.error(f"FFmpeg stderr:\n{e.stderr}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error creating preview video: {e}")
        sys.exit(1)


def main():
    """Main function to run the quick preview pipeline."""
    print("=" * 60)
    print("Quick Preview Tool for Reddit Title Card UI Testing")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Generate title card with mock data
        title_card_path = generate_mock_title_card()
        
        # Step 2: Create 3-second preview video
        preview_path = create_3s_preview_video(title_card_path)
        
        # Success summary
        print()
        print("🎉 SUCCESS! Quick preview completed.")
        print(f"   Title card: {title_card_path}")
        print(f"   Preview video: {preview_path}")
        print()
        print("You can now open 'preview_output.mp4' to see your UI changes")
        print("in a real 1080x1920 video frame.")
        print()
        print("To test different UI changes:")
        print("1. Modify HTML/CSS templates in backend_v2/templates/")
        print("2. Run: python quick_preview.py")
        print("3. Check preview_output.mp4 (should render in under 5 seconds)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()