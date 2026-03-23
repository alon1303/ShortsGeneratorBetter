
import asyncio
import logging
import sys
import os
from pathlib import Path

# Fix path logic to support running from both root and backend_v2
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(current_dir) == "backend_v2":
    sys.path.append(current_dir)
    from reddit_story.reddit_client import RedditClient
    from reddit_story.story_processor import StoryProcessor
    from reddit_story.tts_router import generate_title_and_story_audio
    from reddit_story.video_composer import VideoComposer
    from reddit_story.keyword_extractor import keyword_extractor
    from reddit_story.image_generator_new import RedditImageGenerator
else:
    sys.path.append(os.path.join(current_dir, "backend_v2"))
    from backend_v2.reddit_story.reddit_client import RedditClient
    from backend_v2.reddit_story.story_processor import StoryProcessor
    from backend_v2.reddit_story.tts_router import generate_title_and_story_audio
    from backend_v2.reddit_story.video_composer import VideoComposer
    from backend_v2.reddit_story.keyword_extractor import keyword_extractor
    from backend_v2.reddit_story.image_generator_new import RedditImageGenerator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_full_ai_pipeline(url: str):
    logger.info(f"Starting full pipeline test for URL: {url}")
    
    # 1. Fetch Story
    reddit_client = RedditClient()
    story = await reddit_client.fetch_story_from_url(url)
    if not story:
        logger.error("Failed to fetch story from Reddit.")
        return

    logger.info(f"Fetched story: '{story.title}' ({story.word_count} words)")
    
    # 2. Process Story with AI
    processor = StoryProcessor()
    processed_story = await processor.process_story(story)
    
    logger.info("\n--- AI Splitting Results ---")
    logger.info(f"Total Parts: {processed_story.total_parts}")
    logger.info(f"Detected Gender: {processed_story.detected_gender}")
    logger.info(f"Detected Age: {processed_story.detected_age}")
    
    # 3. Extract Keywords for Title Card
    title_keywords = await keyword_extractor.extract_keywords(story.title)
    
    # 4. Generate Title Card Image
    image_gen = RedditImageGenerator()
    title_card_path = Path("title_card_test.png")
    await image_gen.generate_reddit_post_image(
        title=story.title,
        subreddit=story.subreddit,
        score=story.score,
        author=story.author or "RedditUser",
        output_path=title_card_path,
        custom_keywords=title_keywords
    )
    
    # 5. Generate Audio with Title Card Sync
    logger.info("\n--- Starting Full Video Generation ---")
    
    story_texts = [p.text for p in processed_story.parts]
    
    # generate_title_and_story_audio handles the title card narration and first part merge
    title_audio_path, audio_chunks, subtitle_start_time, timing_data = await generate_title_and_story_audio(
        title=story.title,
        story_text_chunks=story_texts,
        gender=processed_story.detected_gender
    )
    
    composer = VideoComposer()
    output_files = []
    
    # In current architecture, we process parts sequentially
    for i, chunk in enumerate(audio_chunks):
        logger.info(f"\nGenerating Video for Part {i+1}/{len(audio_chunks)}...")
        try:
            # Add AI metadata to chunk for composer/subtitle generator
            part_ai_data = processed_story.parts[i]
            
            # Create video for this part
            output_path = Path(f"output_part_{i+1}.mp4")
            
            # Using create_video_part which is more flexible for individual parts
            result_path = composer.create_video_part(
                audio_chunk=chunk,
                output_path=output_path,
                overlay_image_path=title_card_path if chunk.is_first_part else None,
                timing_data=timing_data if chunk.is_first_part else None,
                custom_keywords=part_ai_data.power_words
            )
            
            if result_path:
                logger.info(f"SUCCESS: Part {i+1} Video generated at: {result_path}")
                output_files.append(result_path)
            else:
                logger.error(f"FAILED: Part {i+1} generation returned no path")
                
        except Exception as e:
            logger.error(f"FAILED: Part {i+1} generation error: {e}")
            import traceback
            logger.error(traceback.format_exc())

    logger.info("\n--- Pipeline Completed ---")
    logger.info(f"Successfully generated {len(output_files)} videos.")
    for f in output_files:
        logger.info(f" - {f}")

if __name__ == "__main__":
    test_url = "https://www.reddit.com/r/AITAH/comments/1rvbmez/aitah_for_cutting_off_my_son_after_his_mom_passed/"
    asyncio.run(test_full_ai_pipeline(test_url))
