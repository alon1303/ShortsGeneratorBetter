
import asyncio
import logging
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend_v2 to path
sys.path.append(str(Path(__file__).parent))

from config.settings import settings
from reddit_story.models import AudioChunk, WordTimestamp
from reddit_story.reddit_client import RedditStory
from reddit_story.video_composer import VideoComposer
from reddit_story.image_generator_new import RedditImageGenerator
from reddit_story.story_processor import StoryProcessor
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_mock_pipeline():
    logger.info("Starting MOCK PIPELINE test...")
    
    # 1. Setup paths to cached assets
    cache_base = settings.CACHE_DIR / "elevenlabs" / "voices"
    cache_id = "1da42763580f7d1ac330c3ba521b4d84_1774258959"
    cached_mp3 = cache_base / f"{cache_id}.mp3"
    cached_json = cache_base / f"{cache_id}.json"
    
    if not cached_mp3.exists() or not cached_json.exists():
        logger.error(f"Cached files not found at {cache_base}. Please ensure they exist.")
        return

    # 2. Load cached timestamps and reconstruct text
    with open(cached_json, 'r') as f:
        word_data = json.load(f)
    
    reconstructed_text = " ".join([w['word'] for w in word_data])
    word_timestamps = [
        WordTimestamp(word=w['word'], start=w['start'], end=w['end'], confidence=w.get('confidence', 1.0))
        for w in word_data
    ]
    
    # Calculate durations
    audio_duration = word_timestamps[-1].end if word_timestamps else 10.0
    
    # 3. Create Mock Reddit Story
    mock_story = RedditStory(
        id="mock_post_123",
        title="I have been my son's dad since he was one",
        text=reconstructed_text,
        subreddit="TrueOffMyChest",
        url="https://reddit.com/r/mock/123",
        score=5000,
        upvote_ratio=1.0,
        created_utc=0,
        author="MockAuthor",
        is_nsfw=False,
        word_count=len(reconstructed_text.split()),
        estimated_duration=audio_duration
    )
    
    # 4. Mock AI and Network settings
    # We'll mock GEMINI_API_KEY to be None to disable AI keywords
    settings.GEMINI_API_KEY = None
    settings.TTS_ENGINE = "elevenlabs"   # Match the cache source
    
    # 5. Create Output Directory for this test
    test_output_dir = settings.OUTPUT_DIR / "test_mock_run"
    if test_output_dir.exists():
        shutil.rmtree(test_output_dir)
    test_output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step A: Story Processing (Local logic, no API)
        processor = StoryProcessor()
        processed_story = await processor.process_story(mock_story, split_into_parts=False)
        logger.info("Story processing completed.")
        
        # Step B: Title Card Generation (Uses Playwright, local browser)
        image_gen = RedditImageGenerator()
        title_card_path = test_output_dir / "title_card.png"
        await image_gen.generate_reddit_post_image(
            title=mock_story.title,
            subreddit=mock_story.subreddit,
            score=mock_story.score,
            author=mock_story.author,
            output_path=title_card_path
        )
        logger.info(f"Title card generated at {title_card_path}")
        
        # Step C: Use cached files
        # We simulate the result of generate_title_and_story_audio
        # Since we are testing backgrounds, we just need a valid AudioChunk
        
        # We'll create a single chunk representing the whole story
        audio_chunk = AudioChunk(
            chunk_id=cache_id,
            text=reconstructed_text,
            audio_path=cached_mp3,
            duration_seconds=audio_duration,
            voice_id="adam",
            file_size_bytes=cached_mp3.stat().st_size,
            word_timestamps=word_timestamps,
            is_first_part=True
        )
        
        # Dummy timing data for the video composer
        timing_data = {
            "title_audio_duration": 2.0, # Approximate title length
            "buffer_seconds": 1.0,
            "title_word_count": 10,
            "subtitle_start_time": 3.0,
            "pop_in_duration": 0.6,
            "pop_out_duration": 0.8,
            "card_start_time": 0.0,
            "card_end_time": 3.0
        }
        
        # Step D: Video Composition (The main thing we want to test)
        logger.info("Starting Video Composition with cached assets...")
        composer = VideoComposer()
        
        final_video_path = test_output_dir / "mock_final_video.mp4"
        
        # Run composition
        # Note: We are bypassing the merged audio part and just feeding the chunk
        # to see if backgrounds and subtitles work.
        result_path = composer.create_video_part(
            audio_chunk=audio_chunk,
            theme="gta", # Test with a specific theme
            output_path=final_video_path,
            overlay_image_path=title_card_path,
            timing_data=timing_data,
            pop_sfx_path=settings.ASSETS_DIR / "sfx" / "pop.wav"
        )
        
        if result_path and result_path.exists():
            logger.info(f"SUCCESS! Video generated at: {result_path}")
            logger.info("The video should have GTA backgrounds and synchronized subtitles from cache.")
        else:
            logger.error("Video generation failed.")
            
    except Exception as e:
        logger.exception(f"Error during mock test: {e}")
    finally:
        logger.info("Test finished. Output available in: " + str(test_output_dir))

if __name__ == "__main__":
    asyncio.run(test_mock_pipeline())
