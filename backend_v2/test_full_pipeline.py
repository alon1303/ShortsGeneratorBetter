
import asyncio
import logging
from pathlib import Path
import sys

# Add backend_v2 to path
sys.path.append(str(Path(__file__).parent))

from auto_pipeline import AutoPipeline
from config.settings import settings

async def test_full_pipeline():
    # Configure logging to see the full process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting FULL PIPELINE test for a single video...")
    
    # Initialize the pipeline with settings for a single cycle, no upload
    pipeline = AutoPipeline(
        # Use a broader list of subreddits to ensure we find stories
        subreddits=["AmItheAsshole", "tifu", "TrueOffMyChest", "pettyrevenge", "EntitledParents"],
        stories_per_run=1,             # Only process one story
        max_video_duration_minutes=2,  # Limit duration for faster testing
        upload_to_youtube=False,        # Disable upload for test
        skip_processed_posts=False      # Don't skip during test
    )
    
    try:
        # Initialize components (Reddit client, etc.)
        success = await pipeline.initialize()
        if not success:
            logger.error("Failed to initialize pipeline components")
            return

        # Run a single cycle
        logger.info("Running a single pipeline cycle...")
        results = await pipeline.run_single_cycle()
        
        # Check results
        if results['stories_successful'] > 0:
            logger.info("SUCCESS: Full pipeline completed for at least one video!")
            for story in results['processed_stories']:
                if story['success']:
                    logger.info(f"Generated video for story: {story['title']}")
        else:
            logger.error("FAILED: No videos were successfully generated.")
            if results['errors']:
                logger.error(f"Pipeline errors: {results['errors']}")
            
    except Exception as e:
        logger.exception(f"An unexpected error occurred during the full pipeline test: {e}")
    finally:
        # Ensure cleanup
        await pipeline.cleanup()

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
