"""
End-to-End automation orchestrator for ShortsGenerator project.
Fetches stories, generates videos sequentially, and uploads to YouTube Shorts.
"""

import asyncio
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import sys
import traceback
import signal

# Project imports
from config.settings import settings
from reddit_story.reddit_client import RedditClient, RedditStory
from reddit_story.story_processor import StoryProcessor
from reddit_story.tts_router import generate_title_and_story_audio
from reddit_story.video_composer import VideoComposer, create_shorts_video
from reddit_story.image_generator_new import RedditImageGenerator
from youtube.uploader import YouTubeUploader, AsyncYouTubeUploader, YouTubeUploadResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.OUTPUT_DIR / 'auto_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PipelineStats:
    """Statistics tracker for the automation pipeline."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.total_stories_processed = 0
        self.successful_videos = 0
        self.failed_videos = 0
        self.quota_exceeded = 0
        self.network_errors = 0
        self.processing_errors = 0
        self.upload_errors = 0
        self.story_durations = []
        self.video_durations = []
        
        # Create stats file
        self.stats_file = settings.DATA_DIR / "pipeline_stats.json"
        self._load_stats()
    
    def _load_stats(self):
        """Load previous stats from file."""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.total_stories_processed = data.get('total_stories_processed', 0)
                    self.successful_videos = data.get('successful_videos', 0)
                    self.failed_videos = data.get('failed_videos', 0)
        except Exception as e:
            logger.warning(f"Could not load stats: {e}")
    
    def save_stats(self):
        """Save current stats to file."""
        try:
            data = {
                'total_stories_processed': self.total_stories_processed,
                'successful_videos': self.successful_videos,
                'failed_videos': self.failed_videos,
                'quota_exceeded': self.quota_exceeded,
                'network_errors': self.network_errors,
                'processing_errors': self.processing_errors,
                'upload_errors': self.upload_errors,
                'last_updated': datetime.now().isoformat(),
                'runtime_hours': (datetime.now() - self.start_time).total_seconds() / 3600,
                'average_story_duration': self.average_story_duration,
                'average_video_duration': self.average_video_duration,
                'success_rate': self.success_rate,
            }
            
            with open(self.stats_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save stats: {e}")
    
    @property
    def average_story_duration(self) -> float:
        """Average story duration in seconds."""
        if self.story_durations:
            return sum(self.story_durations) / len(self.story_durations)
        return 0.0
    
    @property
    def average_video_duration(self) -> float:
        """Average video duration in seconds."""
        if self.video_durations:
            return sum(self.video_durations) / len(self.video_durations)
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_stories_processed == 0:
            return 0.0
        return (self.successful_videos / self.total_stories_processed) * 100
    
    def add_story_processed(self, success: bool, story_duration: float = 0, video_duration: float = 0):
        """Add a processed story to stats."""
        self.total_stories_processed += 1
        
        if success:
            self.successful_videos += 1
            if story_duration > 0:
                self.story_durations.append(story_duration)
            if video_duration > 0:
                self.video_durations.append(video_duration)
        else:
            self.failed_videos += 1
        
        self.save_stats()
    
    def add_error(self, error_type: str):
        """Add error to stats."""
        if error_type == 'quota':
            self.quota_exceeded += 1
        elif error_type == 'network':
            self.network_errors += 1
        elif error_type == 'processing':
            self.processing_errors += 1
        elif error_type == 'upload':
            self.upload_errors += 1
        
        self.save_stats()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            'runtime': str(datetime.now() - self.start_time),
            'total_stories_processed': self.total_stories_processed,
            'successful_videos': self.successful_videos,
            'failed_videos': self.failed_videos,
            'success_rate': f"{self.success_rate:.1f}%",
            'average_story_duration': f"{self.average_story_duration:.1f}s",
            'average_video_duration': f"{self.average_video_duration:.1f}s",
            'quota_exceeded': self.quota_exceeded,
            'network_errors': self.network_errors,
            'processing_errors': self.processing_errors,
            'upload_errors': self.upload_errors,
        }


class AutoPipeline:
    """End-to-End automation orchestrator for ShortsGenerator."""
    
    def __init__(
        self,
        subreddits: Optional[List[str]] = None,
        stories_per_run: int = 3,
        max_video_duration_minutes: int = 3,
        theme: Optional[str] = None,
        voice_id: Optional[str] = None,
        upload_to_youtube: bool = True,
        youtube_privacy_status: str = "private",  # private, public, unlisted
        delay_between_uploads_seconds: int = 300,  # 5 minutes
        max_retries_per_story: int = 2,
        skip_processed_posts: bool = True,
        data_dir: Optional[Path] = None,
        bg_music_path: Optional[Path] = None,
    ):
        """
        Initialize the automation pipeline.
        
        Args:
            subreddits: List of subreddits to fetch stories from
            stories_per_run: Maximum number of stories to process per run
            max_video_duration_minutes: Maximum video duration in minutes
            theme: Background theme for videos
            voice_id: TTS voice ID
            upload_to_youtube: Whether to upload videos to YouTube
            youtube_privacy_status: YouTube privacy status
            delay_between_uploads_seconds: Delay between YouTube uploads
            max_retries_per_story: Maximum retries for failed story processing
            skip_processed_posts: Skip posts already in duplicate prevention system
            data_dir: Directory for storing pipeline data
            bg_music_path: Path to background music file
        """
        # Configuration
        self.subreddits = subreddits or ["AmItheAsshole", "tifu", "TrueOffMyChest", "pettyrevenge", "EntitledParents"]
        self.stories_per_run = stories_per_run
        self.max_video_duration = max_video_duration_minutes * 60
        self.theme = theme or settings.DEFAULT_BACKGROUND_THEME
        self.voice_id = voice_id or settings.DEFAULT_VOICE_ID
        self.bg_music_path = bg_music_path or settings.DEFAULT_BGM_PATH
        self.upload_to_youtube = upload_to_youtube
        self.youtube_privacy_status = youtube_privacy_status
        self.delay_between_uploads = delay_between_uploads_seconds
        self.max_retries = max_retries_per_story
        self.skip_processed_posts = skip_processed_posts
        
        # Data directory
        if data_dir is None:
            self.data_dir = settings.DATA_DIR / "pipeline"
        else:
            self.data_dir = Path(data_dir)
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Components
        self.reddit_client = None
        self.youtube_uploader = None
        self.async_youtube_uploader = None
        self.stats = PipelineStats()
        
        # State
        self.is_running = False
        self.last_upload_time = None
        
        logger.info(f"AutoPipeline initialized with {len(self.subreddits)} subreddits")
        logger.info(f"  Stories per run: {self.stories_per_run}")
        logger.info(f"  Max video duration: {max_video_duration_minutes}min")
        logger.info(f"  Theme: {self.theme}")
        logger.info(f"  Upload to YouTube: {upload_to_youtube}")
        logger.info(f"  YouTube privacy: {youtube_privacy_status}")
        logger.info(f"  Delay between uploads: {delay_between_uploads_seconds}s")
        logger.info(f"  Data directory: {self.data_dir}")
    
    async def initialize(self):
        """Initialize pipeline components."""
        try:
            logger.info("Initializing pipeline components...")
            
            # Initialize Reddit client
            self.reddit_client = RedditClient()
            await self.reddit_client.initialize()
            logger.info("Reddit client initialized")
            
            # Initialize YouTube uploader if needed
            if self.upload_to_youtube:
                self.youtube_uploader = YouTubeUploader()
                self.async_youtube_uploader = AsyncYouTubeUploader(self.youtube_uploader)
                
                # Test credentials
                if not self.youtube_uploader.validate_credentials():
                    logger.warning("YouTube credentials not valid. Starting OAuth2 flow...")
                    service = self.youtube_uploader.get_authenticated_service()
                    if not service:
                        logger.error("Failed to authenticate with YouTube API")
                        logger.warning("YouTube uploads will be disabled")
                        self.upload_to_youtube = False
                    else:
                        logger.info("YouTube uploader authenticated successfully")
                else:
                    logger.info("YouTube credentials are valid")
            
            logger.info("Pipeline initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup pipeline resources."""
        try:
            if self.reddit_client:
                await self.reddit_client.close()
                logger.debug("Reddit client closed")
            
            # Stats are auto-saved on updates
            logger.info("Pipeline cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def fetch_stories(self) -> List[RedditStory]:
        """
        Fetch trending stories from configured subreddits.
        
        Returns:
            List of RedditStory objects
        """
        try:
            logger.info(f"Fetching trending stories from {len(self.subreddits)} subreddits...")
            
            stories = await self.reddit_client.fetch_trending_stories(
                subreddit=self.subreddits,
                time_filter="day",
                limit=self.stories_per_run * 2,  # Fetch extra to filter
                min_score=settings.MIN_STORY_SCORE,
                min_text_length=settings.MIN_STORY_LENGTH,
                max_text_length=settings.MAX_STORY_LENGTH,
                exclude_nsfw=settings.EXCLUDE_NSFW,
                exclude_processed=self.skip_processed_posts,
            )
            
            # Filter by estimated duration
            filtered_stories = []
            for story in stories:
                if story.estimated_duration <= self.max_video_duration:
                    filtered_stories.append(story)
                else:
                    logger.debug(f"Skipping story '{story.title[:50]}...' - too long ({story.estimated_duration:.1f}s)")
            
            # Limit to requested number
            filtered_stories = filtered_stories[:self.stories_per_run]
            
            logger.info(f"Fetched {len(filtered_stories)} stories (filtered from {len(stories)})")
            
            if filtered_stories:
                for i, story in enumerate(filtered_stories, 1):
                    logger.info(f"  {i}. r/{story.subreddit}: '{story.title[:50]}...' ({story.score} upvotes, {story.estimated_duration:.1f}s)")
            
            return filtered_stories
            
        except Exception as e:
            logger.error(f"Failed to fetch stories: {e}")
            self.stats.add_error('network')
            return []
    
    async def process_story(self, story: RedditStory) -> Optional[Path]:
        """
        Process a single Reddit story into a video.
        
        Args:
            story: RedditStory to process
        
        Returns:
            Path to created video file, or None if failed
        """
        logger.info(f"Processing story: '{story.title[:50]}...'")
        
        try:
            # Step 1: Process story into parts
            processor = StoryProcessor(
                min_part_duration=settings.MIN_PART_DURATION,
                max_part_duration=settings.MAX_PART_DURATION,
                max_parts=settings.MAX_PARTS,
            )
            
            processed_story = processor.process_story(story, split_into_parts=True)
            logger.info(f"Story split into {processed_story.total_parts} parts")
            
            # Step 2: Create post-specific folder
            import re
            sanitized_title = re.sub(r'[^\w\s-]', '', story.title).strip().replace(' ', '_')
            sanitized_title = sanitized_title[:50]  # Limit length
            
            post_folder_name = f"{sanitized_title}_{story.id[:8]}"
            post_output_dir = settings.OUTPUT_DIR / "reddit_stories" / post_folder_name
            post_output_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created post-specific folder: {post_output_dir}")
            
            # Step 3: Generate title card
            title_card_generator = RedditImageGenerator()
            title_card_path = post_output_dir / "title_card.png"
            
            output_path = await title_card_generator.generate_reddit_post_image(
                title=story.title,
                subreddit=story.subreddit,
                score=story.score,
                author=story.author,
                theme_mode="dark",
                output_path=title_card_path
            )
            
            if not output_path or not title_card_path.exists():
                raise RuntimeError(f"Failed to generate title card: {title_card_path}")
            
            logger.info(f"Title card generated: {title_card_path}")
            
            # Step 4: Extract text chunks and add CTAs for audience retention
            text_chunks = []
            for i, part in enumerate(processed_story.parts, 1):
                text = part.text
                
                # Add Call To Action at the end of every chunk EXCEPT the last one
                if i < len(processed_story.parts):
                    cta = f" Like and subscribe for part {i + 1}!"
                    text += cta
                    logger.debug(f"Added CTA to part {i}: '{cta}'")
                
                text_chunks.append(text)
            
            # Step 5: Generate title and story audio with timing data
            final_audio_path, story_audio_chunks, title_duration, timing_data = await generate_title_and_story_audio(
                title=story.title,
                story_text_chunks=text_chunks,
                voice=self.voice_id,
                title_voice=self.voice_id,
                engine=settings.TTS_ENGINE.lower(),
                buffer_seconds=0.0,
            )
            
            logger.info(f"Audio generated: {len(story_audio_chunks)} parts, title: {title_duration:.2f}s")
            
            # Step 6: Create separate video parts in post-specific folder
            composer = VideoComposer()
            
            video_parts = []
            for i, audio_chunk in enumerate(story_audio_chunks, 1):
                logger.info(f"Creating video part {i}/{len(story_audio_chunks)}")
                
                # Skip chunks with 0.0s duration
                if audio_chunk.duration_seconds <= 0:
                    logger.warning(f"Skipping audio chunk {i} with 0.0s duration")
                    continue
                
                # Create unique part path
                part_filename = f"part_{i}.mp4"
                part_path = post_output_dir / part_filename
                
                try:
                    # For the first part, include title card with timing data
                    if i == 1:
                        video_part = composer.create_video_part(
                            audio_chunk=audio_chunk,
                            theme=self.theme,
                            output_path=part_path,
                            overlay_image_path=title_card_path,
                            pop_sfx_path=None,  # Optional: add pop SFX if available
                            timing_data=timing_data,
                            bg_music_path=self.bg_music_path
                        )
                    else:
                        video_part = composer.create_video_part(
                            audio_chunk=audio_chunk,
                            theme=self.theme,
                            output_path=part_path,
                            overlay_image_path=None,
                            pop_sfx_path=None,
                            timing_data=None,
                            bg_music_path=self.bg_music_path
                        )
                    
                    video_parts.append(video_part)
                    logger.info(f"Video part {i} created: {video_part}")
                    
                except Exception as e:
                    logger.error(f"Failed to create video part {i}: {e}")
                    # Continue with remaining parts
                    continue
            
            if not video_parts:
                raise ValueError("Failed to create video parts")
            
            # Step 7: Concatenate all parts into final video
            if len(video_parts) == 1:
                # Only one part, use it as final video
                final_video_path = post_output_dir / f"{post_folder_name}_final.mp4"
                import shutil
                shutil.copy2(video_parts[0], final_video_path)
                logger.info(f"Single part copied to final video: {final_video_path}")
            else:
                # Concatenate multiple parts
                final_video_path = post_output_dir / f"{post_folder_name}_final.mp4"
                success = composer.concatenate_videos(video_parts, final_video_path)
                
                if not success:
                    raise RuntimeError(f"Failed to concatenate video parts into {final_video_path}")
                
                logger.info(f"Concatenated {len(video_parts)} parts into final video: {final_video_path}")
            
            # Get video duration
            try:
                import subprocess
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(final_video_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                video_duration = float(result.stdout.strip()) if result.stdout else 0
                logger.info(f"Final video duration: {video_duration:.1f}s")
            except Exception as e:
                logger.warning(f"Could not get video duration: {e}")
                video_duration = 0
            
            # Step 8: Mark post as processed (duplicate prevention)
            self.reddit_client.mark_post_as_processed(story.id)
            logger.info(f"Marked post {story.id} as processed in duplicate prevention system")
            
            # Add to stats
            self.stats.add_story_processed(
                success=True,
                story_duration=story.estimated_duration,
                video_duration=video_duration,
            )
            
            logger.info(f"Story processed successfully: {final_video_path}")
            return final_video_path
            
        except Exception as e:
            logger.error(f"Failed to process story '{story.title[:50]}...': {e}")
            logger.error(traceback.format_exc())
            self.stats.add_error('processing')
            self.stats.add_story_processed(success=False)
            return None
    
    async def upload_to_youtube_if_enabled(self, video_path: Path, story: RedditStory) -> Optional[YouTubeUploadResult]:
        """
        Upload video to YouTube if enabled.
        
        Args:
            video_path: Path to video file
            story: Original Reddit story
        
        Returns:
            YouTubeUploadResult or None if upload not attempted
        """
        if not self.upload_to_youtube:
            logger.info("YouTube upload disabled, skipping")
            return None
        
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None
        
        # Check rate limiting
        if self.last_upload_time:
            time_since_last_upload = (datetime.now() - self.last_upload_time).total_seconds()
            if time_since_last_upload < self.delay_between_uploads:
                wait_time = self.delay_between_uploads - time_since_last_upload
                logger.info(f"Rate limiting: waiting {wait_time:.0f}s before next upload")
                await asyncio.sleep(wait_time)
        
        try:
            # Generate YouTube metadata - truncate title to fit YouTube's 100 character limit
            raw_title = f"{story.title} #shorts"
            title = self.youtube_uploader.truncate_title_for_youtube(raw_title)
            
            description = self.youtube_uploader.generate_description(
                story_title=story.title,
                subreddit=story.subreddit,
                reddit_url=story.url,
                video_parts=1,  # Assuming single video for now
            )
            tags = self.youtube_uploader.generate_default_tags(story.subreddit, story.title)
            
            logger.info(f"Uploading to YouTube: '{title[:50]}...'")
            logger.info(f"  Video: {video_path.name} ({video_path.stat().st_size / (1024*1024):.1f} MB)")
            logger.info(f"  Tags: {len(tags)} tags")
            
            # Upload
            result = await self.async_youtube_uploader.upload_video_async(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id="22",  # People & Blogs
                privacy_status=self.youtube_privacy_status,
                notify_subscribers=False,
                is_shorts=True,
            )
            
            # Update last upload time
            self.last_upload_time = datetime.now()
            
            if result.success:
                logger.info(f"YouTube upload successful!")
                logger.info(f"  Video ID: {result.video_id}")
                logger.info(f"  Video URL: {result.video_url}")
            else:
                logger.error(f"YouTube upload failed: {result.error_message}")
                if result.quota_exceeded:
                    logger.error("YouTube API quota exceeded! Consider reducing upload frequency")
                    self.stats.add_error('quota')
                else:
                    self.stats.add_error('upload')
            
            return result
            
        except Exception as e:
            logger.error(f"YouTube upload error: {e}")
            logger.error(traceback.format_exc())
            self.stats.add_error('upload')
            return YouTubeUploadResult(
                success=False,
                error_message=str(e),
            )
    
    async def process_story_with_retry(self, story: RedditStory) -> bool:
        """
        Process a story with retry logic.
        
        Args:
            story: RedditStory to process
        
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Processing story attempt {attempt + 1}/{self.max_retries + 1}")
                
                # Process story
                video_path = await self.process_story(story)
                
                if not video_path:
                    if attempt < self.max_retries:
                        wait_time = (attempt + 1) * 30  # Exponential backoff
                        logger.warning(f"Story processing failed, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Story processing failed after {self.max_retries + 1} attempts")
                        return False
                
                # Upload to YouTube if enabled
                if self.upload_to_youtube:
                    upload_result = await self.upload_to_youtube_if_enabled(video_path, story)
                    if upload_result and not upload_result.success:
                        logger.warning(f"YouTube upload failed but video was created: {video_path}")
                        # Still count as success since video was created
                        return True
                
                return True
                
            except Exception as e:
                logger.error(f"Error processing story (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    wait_time = (attempt + 1) * 30
                    logger.warning(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    return False
        
        return False
    
    async def run_single_cycle(self) -> Dict[str, Any]:
        """
        Run a single cycle of the automation pipeline.
        
        Returns:
            Dictionary with cycle results
        """
        cycle_start = datetime.now()
        logger.info("=" * 60)
        logger.info(f"Starting pipeline cycle at {cycle_start}")
        logger.info("=" * 60)
        
        results = {
            'cycle_start': cycle_start.isoformat(),
            'stories_fetched': 0,
            'stories_processed': 0,
            'stories_successful': 0,
            'stories_failed': 0,
            'youtube_uploads': 0,
            'youtube_successful': 0,
            'youtube_failed': 0,
            'errors': [],
            'processed_stories': [],
            'cycle_duration': 0,
        }
        
        try:
            # Fetch stories
            stories = await self.fetch_stories()
            results['stories_fetched'] = len(stories)
            
            if not stories:
                logger.warning("No stories fetched, ending cycle early")
                results['errors'].append("No stories fetched")
                return results
            
            # Process each story
            for i, story in enumerate(stories, 1):
                logger.info(f"Processing story {i}/{len(stories)}: '{story.title[:50]}...'")
                results['stories_processed'] += 1
                
                success = await self.process_story_with_retry(story)
                
                if success:
                    results['stories_successful'] += 1
                    results['processed_stories'].append({
                        'id': story.id,
                        'title': story.title,
                        'subreddit': story.subreddit,
                        'url': story.url,
                        'success': True,
                        'timestamp': datetime.now().isoformat(),
                    })
                    logger.info(f"Story {i} processed successfully")
                else:
                    results['stories_failed'] += 1
                    results['processed_stories'].append({
                        'id': story.id,
                        'title': story.title,
                        'subreddit': story.subreddit,
                        'url': story.url,
                        'success': False,
                        'timestamp': datetime.now().isoformat(),
                    })
                    logger.error(f"Story {i} processing failed")
                
                # Small delay between stories to avoid rate limiting
                if i < len(stories):
                    await asyncio.sleep(5)
            
            logger.info(f"Cycle complete: {results['stories_successful']}/{results['stories_processed']} successful")
            
        except Exception as e:
            logger.error(f"Error in pipeline cycle: {e}")
            logger.error(traceback.format_exc())
            results['errors'].append(str(e))
        
        finally:
            cycle_end = datetime.now()
            results['cycle_end'] = cycle_end.isoformat()
            results['cycle_duration'] = (cycle_end - cycle_start).total_seconds()
            
            logger.info("=" * 60)
            logger.info(f"Cycle completed in {results['cycle_duration']:.1f}s")
            logger.info(f"  Stories: {results['stories_successful']}/{results['stories_processed']} successful")
            logger.info(f"  YouTube: {results['youtube_successful']}/{results['youtube_uploads']} successful")
            logger.info("=" * 60)
            
            # Save cycle results
            self._save_cycle_results(results)
        
        return results
    
    def _save_cycle_results(self, results: Dict[str, Any]):
        """Save cycle results to file."""
        try:
            results_file = self.data_dir / f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.debug(f"Cycle results saved: {results_file}")
        except Exception as e:
            logger.error(f"Could not save cycle results: {e}")
    
    async def run_continuous(
        self,
        interval_minutes: int = 60,
        max_cycles: Optional[int] = None,
        stop_on_quota_exceeded: bool = True,
    ):
        """
        Run the pipeline continuously with specified interval.
        
        Args:
            interval_minutes: Minutes between cycles
            max_cycles: Maximum number of cycles to run (None for unlimited)
            stop_on_quota_exceeded: Stop if YouTube quota is exceeded
        """
        self.is_running = True
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        cycle_count = 0
        
        try:
            logger.info(f"Starting continuous pipeline with {interval_minutes}min interval")
            logger.info(f"Press Ctrl+C to stop")
            
            while self.is_running:
                if max_cycles and cycle_count >= max_cycles:
                    logger.info(f"Reached maximum cycles ({max_cycles}), stopping")
                    break
                
                cycle_count += 1
                logger.info(f"Starting cycle {cycle_count}")
                
                # Run cycle
                results = await self.run_single_cycle()
                
                # Check if we should stop due to quota exceeded
                if stop_on_quota_exceeded and self.stats.quota_exceeded > 2:
                    logger.error("YouTube quota exceeded multiple times, stopping pipeline")
                    break
                
                # Wait for next cycle unless stopping
                if self.is_running and (not max_cycles or cycle_count < max_cycles):
                    logger.info(f"Waiting {interval_minutes} minutes until next cycle...")
                    
                    # Wait in smaller chunks to allow graceful shutdown
                    wait_seconds = interval_minutes * 60
                    chunk_size = 10  # Check every 10 seconds
                    
                    for _ in range(wait_seconds // chunk_size):
                        if not self.is_running:
                            break
                        await asyncio.sleep(chunk_size)
        
        except Exception as e:
            logger.error(f"Error in continuous pipeline: {e}")
            logger.error(traceback.format_exc())
        
        finally:
            self.is_running = False
            await self.cleanup()
            
            # Print final stats
            logger.info("=" * 60)
            logger.info("Pipeline stopped")
            logger.info("=" * 60)
            self.print_stats()
    
    def print_stats(self):
        """Print pipeline statistics."""
        stats = self.stats.get_summary()
        
        logger.info("Pipeline Statistics:")
        logger.info(f"  Runtime: {stats['runtime']}")
        logger.info(f"  Total stories processed: {stats['total_stories_processed']}")
        logger.info(f"  Successful videos: {stats['successful_videos']}")
        logger.info(f"  Failed videos: {stats['failed_videos']}")
        logger.info(f"  Success rate: {stats['success_rate']}")
        logger.info(f"  Avg story duration: {stats['average_story_duration']}")
        logger.info(f"  Avg video duration: {stats['average_video_duration']}")
        logger.info(f"  YouTube quota exceeded: {stats['quota_exceeded']}")
        logger.info(f"  Network errors: {stats['network_errors']}")
        logger.info(f"  Processing errors: {stats['processing_errors']}")
        logger.info(f"  Upload errors: {stats['upload_errors']}")


async def run_pipeline_from_cli():
    """Run pipeline from command line with configurable arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ShortsGenerator Automation Pipeline')
    parser.add_argument('--subreddits', nargs='+', help='Subreddits to fetch from')
    parser.add_argument('--stories', type=int, default=3, help='Stories per cycle')
    parser.add_argument('--max-duration', type=int, default=3, help='Max video duration in minutes')
    parser.add_argument('--theme', help='Background theme')
    parser.add_argument('--voice', help='TTS voice ID')
    parser.add_argument('--no-upload', action='store_true', help='Disable YouTube upload')
    parser.add_argument('--privacy', default='private', choices=['private', 'public', 'unlisted'],
                       help='YouTube privacy status')
    parser.add_argument('--upload-delay', type=int, default=300, help='Delay between uploads in seconds')
    parser.add_argument('--interval', type=int, default=60, help='Minutes between cycles')
    parser.add_argument('--cycles', type=int, help='Maximum number of cycles')
    parser.add_argument('--single-cycle', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--retries', type=int, default=2, help='Max retries per story')
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = AutoPipeline(
        subreddits=args.subreddits,
        stories_per_run=args.stories,
        max_video_duration_minutes=args.max_duration,
        theme=args.theme,
        voice_id=args.voice,
        upload_to_youtube=not args.no_upload,
        youtube_privacy_status=args.privacy,
        delay_between_uploads_seconds=args.upload_delay,
        max_retries_per_story=args.retries,
    )
    
    # Initialize
    if not await pipeline.initialize():
        logger.error("Failed to initialize pipeline")
        return
    
    try:
        if args.single_cycle:
            # Run single cycle
            await pipeline.run_single_cycle()
            pipeline.print_stats()
        else:
            # Run continuous
            await pipeline.run_continuous(
                interval_minutes=args.interval,
                max_cycles=args.cycles,
            )
    
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    
    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    # Run pipeline from command line
    asyncio.run(run_pipeline_from_cli())