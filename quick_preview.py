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
    
    # Get background video dimensions to decide if scaling is needed
    try:
        dim_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            str(background_path)
        ]
        dim_result = subprocess.run(dim_cmd, capture_output=True, text=True, check=True)
        bg_width, bg_height = map(int, dim_result.stdout.strip().split(','))
        logger.info(f"Background video dimensions: {bg_width}x{bg_height}")
    except Exception as e:
        logger.warning(f"Could not get background dimensions, assuming 1080x1920: {e}")
        bg_width, bg_height = 1080, 1920
    
    # Build FFmpeg filter complex that exactly matches the real pipeline
    # 1. Trim background to exactly 3 seconds
    # 2. Only scale/crop background if not already 1080x1920
    # 3. Scale title card to exactly 80% (matching video_composer.py line 208)
    # 4. Center overlay
    
    # Background processing chain
    bg_filters = ['trim=duration=3', 'setpts=PTS-STARTPTS']
    if bg_width != 1080 or bg_height != 1920:
        logger.info(f"Background is not 1080x1920, scaling and cropping to fit")
        bg_filters.extend([
            'scale=1080:1920:force_original_aspect_ratio=increase',
            'crop=1080:1920'
        ])
    else:
        logger.info("Background is already 1080x1920, using as-is")
    
    bg_filter_chain = ','.join(bg_filters)
    
    # Title card scaling - fixed width of 900px with proportional height
    title_scale = 'scale=900:-1'
    
    # Full filter_complex
    filter_complex = (
        f'[0:v]{bg_filter_chain}[bg];'
        f'[1:v]{title_scale}[overlay_scaled];'
        f'[bg][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:enable=\'between(t,0,3)\'[v]'
    )
    
    # Build FFmpeg command as list of strings (best practice per .clinerules)
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file without asking
        '-i', str(background_path),  # Background video input
        '-i', str(title_card_path),  # Title card image input
        '-filter_complex', filter_complex,
        '-map', '[v]',  # Map video output
        '-an',  # No audio
        '-t', '3',  # Ensure output is exactly 3 seconds
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-movflags', '+faststart',
        str(output_path)
    ]
    
    logger.info(f"Running FFmpeg command to create preview: {output_path}")
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")
    logger.debug(f"Filter complex: {filter_complex}")
    
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
            
            # Verify output dimensions
            try:
                verify_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'csv=p=0',
                    str(output_path)
                ]
                verify_result = subprocess.run(verify_cmd, capture_output=True, text=True, check=True)
                out_width, out_height = map(int, verify_result.stdout.strip().split(','))
                logger.info(f"Output video dimensions: {out_width}x{out_height}")
            except Exception as e:
                logger.warning(f"Could not verify output dimensions: {e}")
            
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