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
import asyncio
import argparse
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

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
from reddit_story.edgetts_client import EdgeTTSClient
from reddit_story.video_composer import VideoComposer
from reddit_story.elevenlabs_client import AudioChunk, WordTimestamp


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
        "body": ""
        
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


async def generate_dummy_audio_with_timestamps() -> AudioChunk:
    """
    Generate dummy audio with EdgeTTS for testing subtitle timing.
    
    Returns:
        AudioChunk with word timestamps
    """
    logger.info("Generating dummy audio with EdgeTTS...")
    
    # Simple text with clear title and story separation
    title_text = "Am I the jerk?"
    story_text = "Here is what happened to me today."
    full_text = f"{title_text} {story_text}"
    
    # Calculate word counts
    title_word_count = len(title_text.split())
    total_word_count = len(full_text.split())
    story_word_count = total_word_count - title_word_count
    
    logger.info(f"Title: '{title_text}' ({title_word_count} words)")
    logger.info(f"Story: '{story_text}' ({story_word_count} words)")
    logger.info(f"Full text: '{full_text}'")
    
    async with EdgeTTSClient() as tts_client:
        # Generate audio with timestamps
        audio_path, duration, word_timestamps = await tts_client.text_to_speech_with_timestamps(
            text=full_text,
            use_cache=True  # Use cache to speed up repeated tests
        )
        
        if not audio_path or not word_timestamps:
            raise RuntimeError("Failed to generate audio with timestamps")
        
        logger.info(f"Audio generated: {duration:.2f}s, {len(word_timestamps)} word timestamps")
        
        # Create AudioChunk
        chunk = AudioChunk(
            chunk_id=str(uuid.uuid4())[:8],
            text=full_text,
            audio_path=audio_path,
            duration_seconds=duration,
            voice_id=tts_client.voice,
            file_size_bytes=audio_path.stat().st_size,
            word_timestamps=word_timestamps
        )
        
        # Log timing information
        if len(word_timestamps) >= title_word_count:
            last_title_word = word_timestamps[title_word_count - 1]
            title_duration = last_title_word.end
            logger.info(f"Title duration (end of last title word): {title_duration:.3f}s")
            
            if len(word_timestamps) > title_word_count:
                first_story_word = word_timestamps[title_word_count]
                logger.info(f"First story word starts at: {first_story_word.start:.3f}s")
        
        return chunk


def create_timing_data(audio_chunk: AudioChunk, title_word_count: int = 4) -> Dict[str, Any]:
    """
    Create timing_data dict exactly as it would be in production.
    
    Args:
        audio_chunk: AudioChunk with word timestamps
        title_word_count: Number of words in the title
    
    Returns:
        timing_data dict with all required fields
    """
    if not audio_chunk.word_timestamps:
        raise ValueError("AudioChunk must have word timestamps")
    
    if title_word_count <= 0 or title_word_count >= len(audio_chunk.word_timestamps):
        raise ValueError(f"Invalid title_word_count: {title_word_count}, total words: {len(audio_chunk.word_timestamps)}")
    
    # Get title duration (end time of last title word)
    last_title_word = audio_chunk.word_timestamps[title_word_count - 1]
    title_duration = last_title_word.end
    
    # Calculate timing values
    card_start_time = 0.0
    card_end_time = title_duration  # Card disappears when title narration ends
    subtitle_start_time = title_duration  # Subtitles start when story begins
    
    # Additional values for TitlePopupTimingCalculator if needed
    buffer_seconds = 0.5  # Buffer before pop-in animation
    pop_in_duration = 0.3  # Duration of pop-in animation
    
    timing_data = {
        # Core timing values
        'card_start_time': card_start_time,
        'card_end_time': card_end_time,
        'subtitle_start_time': subtitle_start_time,
        'title_word_count': title_word_count,
        
        # Additional values for animation
        'title_audio_duration': title_duration,
        'buffer_seconds': buffer_seconds,
        'pop_in_duration': pop_in_duration,
        
        # Metadata
        'total_audio_duration': audio_chunk.duration_seconds,
        'total_word_count': len(audio_chunk.word_timestamps),
        'story_word_count': len(audio_chunk.word_timestamps) - title_word_count,
    }
    
    logger.info("Timing data created:")
    logger.info(f"  Title duration: {title_duration:.3f}s")
    logger.info(f"  Card start: {card_start_time:.3f}s, end: {card_end_time:.3f}s")
    logger.info(f"  Subtitle start: {subtitle_start_time:.3f}s")
    logger.info(f"  Title word count: {title_word_count}")
    
    # Save timing data to file for debugging
    debug_path = Path.cwd() / "timing_debug.json"
    with open(debug_path, 'w') as f:
        json.dump(timing_data, f, indent=2)
    logger.info(f"Timing data saved to: {debug_path}")
    
    return timing_data


async def test_subtitle_timing_logic() -> Path:
    """
    Main test function for subtitle timing logic.
    
    Returns:
        Path to the generated test video
    """
    logger.info("=" * 60)
    logger.info("Testing subtitle timing logic")
    logger.info("=" * 60)
    
    try:
        # Step 1: Generate dummy audio with EdgeTTS
        audio_chunk = await generate_dummy_audio_with_timestamps()
        
        # Step 2: Create timing data (title is 4 words: "Am I the jerk?")
        timing_data = create_timing_data(audio_chunk, title_word_count=4)
        
        # Step 3: Generate or use existing title card
        title_card_path = Path.cwd() / "title_card.png"
        if not title_card_path.exists():
            logger.info("Generating title card...")
            title_card_path = generate_mock_title_card()
        
        # Step 4: Check for background video
        background_path = Path.cwd() / "test_bg.mp4"
        if not background_path.exists():
            # Create a simple color background if test_bg.mp4 doesn't exist
            logger.warning(f"Background video not found: {background_path}")
            logger.info("Creating simple color background...")
            background_path = Path.cwd() / "test_bg_solid.mp4"
            
            if not background_path.exists():
                # Generate a 10-second solid color background
                cmd = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi',
                    '-i', 'color=c=0x1a1a2e:s=1080x1920:d=10',
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    str(background_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to create background: {result.stderr}")
                logger.info(f"Created solid color background: {background_path}")
        
        # Step 5: Create video composer and generate video
        logger.info("Creating video with subtitle timing...")
        composer = VideoComposer()
        
        # Create output path
        output_path = Path.cwd() / "test_timing_preview.mp4"
        
        # Create video part using the timing_data
        video_part = composer.create_video_part(
            audio_chunk=audio_chunk,
            theme="nature",  # Use nature theme for background
            output_path=output_path,
            overlay_image_path=title_card_path,
            pop_sfx_path=None,  # Skip pop SFX for simplicity
            timing_data=timing_data,
            hook_duration=None  # Use timing_data instead
        )
        
        logger.info(f"✅ Test video created successfully: {output_path}")
        
        # Verify the video
        if output_path.exists() and output_path.stat().st_size > 0:
            # Get video duration
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                duration = float(result.stdout.strip())
                logger.info(f"Output video duration: {duration:.2f}s")
            
            # Print summary
            logger.info("\n" + "=" * 60)
            logger.info("TEST COMPLETE - Expected behavior:")
            logger.info(f"1. Title card visible from {timing_data['card_start_time']:.2f}s to {timing_data['card_end_time']:.2f}s")
            logger.info(f"2. Subtitles start at {timing_data['subtitle_start_time']:.2f}s (after title)")
            logger.info(f"3. Subtitles should NOT include title words (filtered {timing_data['title_word_count']} words)")
            logger.info(f"4. Audio duration: {audio_chunk.duration_seconds:.2f}s")
            logger.info(f"5. Output video: {output_path}")
            logger.info("=" * 60)
            
            return output_path
        else:
            raise RuntimeError(f"Output video not created: {output_path}")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


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


async def main_async(args):
    """Async main function to handle different modes."""
    if args.mode == "timing":
        # Run subtitle timing test
        print("=" * 60)
        print("Subtitle Timing Logic Test")
        print("=" * 60)
        print()
        
        try:
            output_path = await test_subtitle_timing_logic()
            
            print()
            print("🎉 TIMING TEST COMPLETE!")
            print(f"Test video created: {output_path}")
            print()
            print("Expected behavior:")
            print("1. Title card appears immediately")
            print("2. Narrator reads title while card is visible")
            print("3. Title card disappears when title narration ends")
            print("4. Subtitles appear ONLY after title ends")
            print("5. Subtitles do NOT include title words")
            print()
            print("Open the video to visually verify the timing:")
            print(f"  {output_path}")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            sys.exit(1)
            
    else:
        # Original preview mode
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


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Quick Preview Tool for Reddit Title Card UI Testing"
    )
    parser.add_argument(
        "--mode",
        choices=["preview", "timing"],
        default="preview",
        help="Mode: 'preview' for UI testing, 'timing' for subtitle timing test"
    )
    
    args = parser.parse_args()
    
    # Run async main function
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()