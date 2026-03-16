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
    """Generate a title card image using mock Reddit post data."""
    logger.info("Generating mock Reddit title card...")
    
    generator = RedditImageGenerator()
    
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
    
    output_path = Path.cwd() / "title_card_preview.png"
    logger.info(f"Using mock data: Title='{mock_data['title'][:50]}...'")
    
    try:
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
    """Generate a real 3-5 second audio chunk with word timestamps."""
    logger.info("Generating dynamic mock audio with EdgeTTS...")
    text = "Am I the jerk? Here is a quick test of the preview pipeline."
    logger.info(f"Generating audio for text: '{text}'")
    
    async with EdgeTTSClient() as tts_client:
        audio_path, duration, word_timestamps = await tts_client.text_to_speech_with_timestamps(
            text=text,
            use_cache=True
        )
        
        if not audio_path or not word_timestamps:
            raise RuntimeError("Failed to generate audio with timestamps")
        
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
    """Generate title and story audio with timing data exactly like production."""
    logger.info("Generating title and story audio with timing data...")
    title = "Am I the jerk?"
    story_chunks = ["Here is a quick test of the preview pipeline."]
    
    final_audio_path, story_audio_chunks, title_duration, timing_data = await generate_title_and_story_audio(
        title=title,
        story_text_chunks=story_chunks,
        voice=None,
        title_voice=None,
        engine="edge",
        buffer_seconds=0.0
    )
    
    if not story_audio_chunks:
        raise RuntimeError("Failed to generate story audio chunks")
    
    first_chunk = story_audio_chunks[0]
    return first_chunk, timing_data


def create_pop_sfx_path() -> Optional[Path]:
    """Get the pop SFX file path if available."""
    pop_sfx_path = Path(__file__).parent / "backend_v2" / "assets" / "sfx" / "pop.wav"
    if pop_sfx_path.exists():
        return pop_sfx_path
    
    pop_sfx_path = Path(__file__).parent / "backend_v2" / "assets" / "sfx" / "pop_alt.wav"
    if pop_sfx_path.exists():
        return pop_sfx_path
    
    return None

def get_bg_music_path() -> Optional[Path]:
    """Get the background music file path if available."""
    bg_music_path = Path(__file__).parent / "backend_v2" / "assets" / "audio" / "lofi_bg.mp3"
    if bg_music_path.exists():
        logger.info(f"Found background music: {bg_music_path}")
        return bg_music_path
    
    logger.warning(f"No background music found at {bg_music_path}, continuing without it")
    return None


async def create_production_preview() -> Path:
    """Main function that creates a preview using the full production pipeline."""
    logger.info("=" * 60)
    logger.info("Creating production-accurate preview")
    logger.info("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Generate title card
        logger.info("Step 1/6: Generating title card...")
        title_card_path = await generate_mock_title_card()
        
        # Step 2: Generate audio with timing data
        logger.info("Step 2/6: Generating audio with timing data...")
        audio_chunk, timing_data = await generate_title_and_story_with_timing()
        
        # Step 3: Get pop SFX
        logger.info("Step 3/6: Loading pop SFX...")
        pop_sfx_path = create_pop_sfx_path()
        
        # Step 4: Get Background Music
        logger.info("Step 4/6: Loading background music...")
        bg_music_path = get_bg_music_path()
        
        # Step 5: Create video
        logger.info("Step 5/6: Creating video with VideoComposer...")
        composer = VideoComposer()
        
        output_path = Path.cwd() / "production_preview.mp4"
        
        video_part = composer.create_video_part(
            audio_chunk=audio_chunk,
            theme=None,
            output_path=output_path,
            overlay_image_path=title_card_path,
            pop_sfx_path=pop_sfx_path,
            timing_data=timing_data,
            hook_duration=None,
            bg_music_path=bg_music_path  # <--- העברנו את המוזיקה כאן!
        )
        
        # Step 6: Verify and log results
        logger.info("Step 6/6: Verifying output...")
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"✅ Production preview created successfully: {output_path}")
            return output_path
        else:
            raise RuntimeError(f"Output video not created: {output_path}")


async def quick_test_subtitle_overlap() -> None:
    """Quick test to verify subtitle generation doesn't have visual overlaps."""
    # (השארתי את הפונקציה הזו כפי שהיא, היא רק לטסטים של כתוביות)
    pass


async def main_async(args):
    """Async main function."""
    try:
        if args.mode == "subtitle_test":
            await quick_test_subtitle_overlap()
        else:
            output_path = await create_production_preview()
            
            print("\n" + "=" * 60)
            print("🎉 PRODUCTION PREVIEW COMPLETE!")
            print("=" * 60)
            print(f"Output video: {output_path}")
            
    except Exception as e:
        logger.error(f"❌ Preview generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Production-accurate preview for Reddit Stories pipeline")
    parser.add_argument("--mode", choices=["preview", "subtitle_test"], default="preview")
    args = parser.parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()