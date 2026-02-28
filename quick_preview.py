#!/usr/bin/env python3
"""
Quick Preview Tool for Reddit Title Card UI Testing
This script generates a 3-5 second preview that perfectly simulates the production video generation pipeline.
It uses all the same classes and methods as the real pipeline in main.py and video_composer.py.
"""

import logging
import sys
import argparse
import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend_v2 to the Python path
backend_path = Path(__file__).parent / "backend_v2"
sys.path.insert(0, str(backend_path))

from reddit_story.image_generator_new import RedditImageGenerator, TitlePopupTimingCalculator
from reddit_story.edgetts_client import EdgeTTSClient
from reddit_story.video_composer import VideoComposer
from reddit_story.background_manager import BackgroundManager
from reddit_story.subtitle_generator import SubtitleGenerator
from reddit_story.audio_mixer import AudioMixer
from reddit_story.tts_router import get_tts_client, generate_title_and_story_audio
from reddit_story.models import AudioChunk, WordTimestamp
from config.settings import settings


async def generate_mock_title_card() -> Path:
    """Generate a title card image using mock Reddit post data.
    
    Returns:
        Path to the generated title card PNG image with transparent background.
    """
    logger.info("Generating mock Reddit title card...")
    
    # Create image generator
    generator = RedditImageGenerator()
    
    # Mock data for testing - similar to production
    mock_data = {
        "title": "Am I the jerk for refusing to give my mom my savings?",
        "subreddit": "AmItheJerk",
        "score": 12500,
        "author": "ThrowRA_SaveAccount",
        "flair": "SERIOUS",
        "comments": 850,
        "theme_mode": "dark",
        "body": ""
    }
    
    # Generate the image
    output_path = Path.cwd() / "title_card_preview.png"
    
    logger.info(f"Using mock data: Title='{mock_data['title'][:50]}...'")
    
    try:
        # Use async method directly
        result_path = await generator.generate_reddit_post_image(
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
            return result_path
        else:
            logger.error("❌ Failed to generate title card")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Error generating title card: {e}")
        sys.exit(1)


async def generate_dynamic_mock_audio() -> AudioChunk:
    """
    Generate a real 3-5 second audio chunk with word timestamps using EdgeTTS.
    
    Returns:
        AudioChunk with word timestamps for use in VideoComposer
    """
    logger.info("Generating dynamic mock audio with EdgeTTS...")
    
    # Text that will produce ~4 seconds of audio
    text = "Am I the jerk? Here is a quick test of the preview pipeline."
    
    logger.info(f"Generating audio for text: '{text}'")
    
    async with EdgeTTSClient() as tts_client:
        # Generate audio with timestamps
        audio_path, duration, word_timestamps = await tts_client.text_to_speech_with_timestamps(
            text=text,
            use_cache=True
        )
        
        if not audio_path or not word_timestamps:
            raise RuntimeError("Failed to generate audio with timestamps")
        
        logger.info(f"Audio generated: {duration:.2f}s, {len(word_timestamps)} word timestamps")
        
        # Create AudioChunk exactly as production expects
        chunk = AudioChunk(
            chunk_id=str(uuid.uuid4())[:8],
            text=text,
            audio_path=audio_path,
            duration_seconds=duration,
            voice_id=tts_client.voice,
            file_size_bytes=audio_path.stat().st_size,
            word_timestamps=word_timestamps
        )
        
        return chunk


async def generate_title_and_story_with_timing() -> Tuple[AudioChunk, Dict[str, Any]]:
    """
    Generate title and story audio with timing data exactly like production.
    
    Returns:
        Tuple of (AudioChunk for first part with title merged, timing_data dict)
    """
    logger.info("Generating title and story audio with timing data...")
    
    title = "Am I the jerk?"
    story_chunks = ["Here is a quick test of the preview pipeline."]
    
    # Use the same function as production (from tts_router)
    final_audio_path, story_audio_chunks, title_duration, timing_data = await generate_title_and_story_audio(
        title=title,
        story_text_chunks=story_chunks,
        voice=None,  # Use default
        title_voice=None,
        engine="edge",
        buffer_seconds=0.0
    )
    
    if not story_audio_chunks:
        raise RuntimeError("Failed to generate story audio chunks")
    
    # The first chunk already has title merged in
    first_chunk = story_audio_chunks[0]
    
    logger.info(f"Generated audio: title={title_duration:.2f}s, total={first_chunk.duration_seconds:.2f}s")
    
    return first_chunk, timing_data


def create_pop_sfx_path() -> Optional[Path]:
    """
    Get the pop SFX file path if available.
    
    Returns:
        Path to pop SFX file, or None if not found
    """
    pop_sfx_path = Path(__file__).parent / "backend_v2" / "assets" / "sfx" / "pop.wav"
    if pop_sfx_path.exists():
        logger.info(f"Found pop SFX: {pop_sfx_path}")
        return pop_sfx_path
    
    # Try alternative
    pop_sfx_path = Path(__file__).parent / "backend_v2" / "assets" / "sfx" / "pop_alt.wav"
    if pop_sfx_path.exists():
        logger.info(f"Found alternative pop SFX: {pop_sfx_path}")
        return pop_sfx_path
    
    logger.warning("No pop SFX found, continuing without it")
    return None


async def create_production_preview() -> Path:
    """
    Main function that creates a 3-5 second preview using the full production pipeline.
    
    Returns:
        Path to the generated preview video
    """
    logger.info("=" * 60)
    logger.info("Creating production-accurate preview")
    logger.info("=" * 60)
    
    # Create temporary directory for all intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Generate title card (HTML to Image with Playwright)
        logger.info("Step 1/5: Generating title card...")
        title_card_path = await generate_mock_title_card()
        
        # Step 2: Generate audio with timing data
        logger.info("Step 2/5: Generating audio with timing data...")
        audio_chunk, timing_data = await generate_title_and_story_with_timing()
        
        # Limit to 4 seconds max for speed
        max_duration = 4.0
        if audio_chunk.duration_seconds > max_duration:
            logger.info(f"Audio duration {audio_chunk.duration_seconds:.1f}s > {max_duration}s, limiting for preview")
            # We'll let the VideoComposer handle duration via background clip
        
        # Step 3: Get pop SFX if available
        logger.info("Step 3/5: Loading pop SFX...")
        pop_sfx_path = create_pop_sfx_path()
        
        # Step 4: Create video using VideoComposer (exactly like production)
        logger.info("Step 4/5: Creating video with VideoComposer...")
        composer = VideoComposer()
        
        # Output path
        output_path = Path.cwd() / "production_preview.mp4"
        
        # Use create_video_part with timing_data for pop-in animation
        # This will use TitlePopupTimingCalculator internally
        video_part = composer.create_video_part(
            audio_chunk=audio_chunk,
            theme=None,  # Random theme
            output_path=output_path,
            overlay_image_path=title_card_path,
            pop_sfx_path=pop_sfx_path,
            timing_data=timing_data,
            hook_duration=None  # Use timing_data instead
        )
        
        # Step 5: Verify and log results
        logger.info("Step 5/5: Verifying output...")
        if output_path.exists() and output_path.stat().st_size > 0:
            # Get video duration
            try:
                import subprocess
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
            except Exception as e:
                logger.warning(f"Could not get video duration: {e}")
            
            logger.info(f"✅ Production preview created successfully: {output_path}")
            logger.info(f"   File size: {output_path.stat().st_size} bytes")
            
            # Log what was included
            logger.info("\n" + "=" * 60)
            logger.info("PREVIEW INCLUDES (Production-accurate):")
            logger.info(f"1. HTML-generated Title Card: {title_card_path}")
            logger.info(f"2. Real Pop-in Animation: Using TitlePopupTimingCalculator")
            logger.info(f"3. Pop SFX Mixed: {'Yes' if pop_sfx_path else 'No'}")
            logger.info(f"4. Dynamic ASS Subtitles: Generated by SubtitleGenerator")
            logger.info(f"5. Real Word Timestamps: {len(audio_chunk.word_timestamps or [])} words")
            logger.info(f"6. Dynamic Background: From BackgroundManager")
            logger.info(f"7. Audio Duration: {audio_chunk.duration_seconds:.2f}s")
            logger.info("=" * 60)
            
            return output_path
        else:
            raise RuntimeError(f"Output video not created: {output_path}")


async def quick_test_subtitle_overlap() -> None:
    """
    Quick test to verify subtitle generation doesn't have visual overlaps.
    Generates ASS subtitles for 1-2 lines and logs timing.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Quick Subtitle Overlap Test")
    logger.info("=" * 60)
    
    # Generate a simple audio chunk
    text = "This is a test to check for subtitle overlaps in the preview."
    async with EdgeTTSClient() as tts_client:
        audio_path, duration, word_timestamps = await tts_client.text_to_speech_with_timestamps(
            text=text,
            use_cache=True
        )
    
    if not word_timestamps:
        logger.warning("No word timestamps generated, skipping subtitle test")
        return
    
    # Create subtitle generator with same settings as production
    generator = SubtitleGenerator(
        video_width=1080,
        video_height=1920,
        max_words_per_phrase=5,
        min_words_per_phrase=2,
        max_phrase_duration=3.0,
        min_gap_between_phrases=0.1
    )
    
    # Generate phrases
    phrases = generator.chunk_words_into_phrases(word_timestamps, duration)
    
    logger.info(f"Generated {len(phrases)} phrases from {len(word_timestamps)} words")
    
    # Check for overlaps
    for i, phrase in enumerate(phrases):
        logger.info(f"Phrase {i+1}: '{phrase.text[:50]}...'")
        logger.info(f"  Timing: {phrase.start_time:.2f}s - {phrase.end_time:.2f}s")
        logger.info(f"  Duration: {phrase.end_time - phrase.start_time:.2f}s")
        logger.info(f"  Words: {len(phrase.words)}")
    
    # Check gaps between phrases
    if len(phrases) > 1:
        for i in range(len(phrases) - 1):
            gap = phrases[i + 1].start_time - phrases[i].end_time
            if gap < 0:
                logger.warning(f"⚠️  OVERLAP DETECTED: Phrase {i+1} ends at {phrases[i].end_time:.2f}s, "
                             f"Phrase {i+2} starts at {phrases[i + 1].start_time:.2f}s "
                             f"(overlap: {-gap:.2f}s)")
            elif gap < generator.min_gap_between_phrases:
                logger.info(f"  Gap between phrase {i+1} and {i+2}: {gap:.2f}s (minimum: {generator.min_gap_between_phrases}s)")
            else:
                logger.info(f"  Gap between phrase {i+1} and {i+2}: {gap:.2f}s")
    
    logger.info("✅ Subtitle overlap test completed")


async def main_async(args):
    """Async main function."""
    try:
        if args.mode == "subtitle_test":
            await quick_test_subtitle_overlap()
        else:
            # Default: production preview
            output_path = await create_production_preview()
            
            print("\n" + "=" * 60)
            print("🎉 PRODUCTION PREVIEW COMPLETE!")
            print("=" * 60)
            print()
            print(f"Output video: {output_path}")
            print()
            print("This preview uses the EXACT SAME pipeline as production:")
            print("  ✓ HTML to Image Title Card (Playwright)")
            print("  ✓ TitlePopupTimingCalculator for pop-in animation")
            print("  ✓ AudioMixer for pop SFX mixing")
            print("  ✓ SubtitleGenerator for ASS subtitles")
            print("  ✓ BackgroundManager for dynamic backgrounds")
            print("  ✓ VideoComposer.create_video_part()")
            print()
            print("To test UI changes:")
            print("1. Modify templates in backend_v2/templates/reddit_post.html")
            print("2. Run: python quick_preview.py")
            print("3. Check production_preview.mp4")
            print()
            
    except Exception as e:
        logger.error(f"❌ Preview generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Production-accurate preview for Reddit Stories pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["preview", "subtitle_test"],
        default="preview",
        help="Mode: 'preview' for full pipeline test, 'subtitle_test' for subtitle overlap check"
    )
    
    args = parser.parse_args()
    
    # Run async main function
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()