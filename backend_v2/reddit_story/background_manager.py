"""
Background Video Manager for Reddit Stories Shorts.
Manages background video selection, cropping, and duration matching.
"""

import random
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import subprocess
import json
import tempfile

from config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class BackgroundManager:
    """Manages background videos for Reddit Stories Shorts."""
    
    def __init__(self, backgrounds_dir: Optional[Path] = None):
        """
        Initialize background manager.
        
        Args:
            backgrounds_dir: Directory containing background videos (defaults to settings.BACKGROUNDS_DIR)
        """
        self.backgrounds_dir = backgrounds_dir or settings.BACKGROUNDS_DIR
        
        # Ensure backgrounds directory exists
        self.backgrounds_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for video metadata
        self._video_cache: Dict[Path, Dict[str, Any]] = {}
        
        logger.info(f"BackgroundManager initialized with directory: {self.backgrounds_dir}")
    
    def get_available_themes(self) -> List[str]:
        """
        Get list of available background themes.
        
        Returns:
            List of theme names
        """
        themes = []
        for item in self.backgrounds_dir.iterdir():
            if item.is_dir():
                themes.append(item.name)
        
        # Fallback to configured themes if directory is empty
        if not themes:
            themes = settings.BACKGROUND_THEMES
        
        return sorted(themes)
    
    def get_backgrounds_by_theme(self, theme: str) -> List[Path]:
        """
        Get all background videos for a specific theme.
        
        Args:
            theme: Theme name (e.g., "minecraft", "abstract")
            
        Returns:
            List of Path objects to background videos
        """
        theme_dir = self.backgrounds_dir / theme
        
        if not theme_dir.exists():
            logger.warning(f"Theme directory does not exist: {theme_dir}")
            return []
        
        video_files = []
        for ext in settings.ALLOWED_EXTENSIONS:
            video_files.extend(list(theme_dir.glob(f"*{ext}")))
        
        # Sort by filename for consistency
        video_files.sort()
        
        logger.debug(f"Found {len(video_files)} background videos for theme '{theme}'")
        return video_files
    
    def get_random_background(self, theme: Optional[str] = None) -> Optional[Path]:
        """
        Get a random background video path.
        
        Args:
            theme: Optional theme to filter by (defaults to random theme)
            
        Returns:
            Path to background video, or None if no backgrounds available
        """
        if theme:
            backgrounds = self.get_backgrounds_by_theme(theme)
        else:
            # Get backgrounds from all themes
            backgrounds = []
            for theme_name in self.get_available_themes():
                backgrounds.extend(self.get_backgrounds_by_theme(theme_name))
        
        if not backgrounds:
            logger.warning("No background videos found")
            return None
        
        return random.choice(backgrounds)

    def get_random_backgrounds(self, count: int, theme: Optional[str] = None) -> List[Path]:
        """
        Select `count` unique background videos randomly.
        If there aren't enough unique videos, allow repetitions.
        
        Args:
            count: Number of background videos to select
            theme: Optional theme to filter by (defaults to random theme)
            
        Returns:
            List of Path objects to selected background videos
        """
        if count <= 0:
            return []
        
        if theme:
            backgrounds = self.get_backgrounds_by_theme(theme)
        else:
            # Get backgrounds from all themes
            backgrounds = []
            for theme_name in self.get_available_themes():
                backgrounds.extend(self.get_backgrounds_by_theme(theme_name))
        
        if not backgrounds:
            logger.warning("No background videos found")
            return []
        
        # Ensure we have unique backgrounds if possible
        unique_backgrounds = list(set(backgrounds))  # Remove duplicates
        if len(unique_backgrounds) >= count:
            selected = random.sample(unique_backgrounds, count)
        else:
            # Not enough unique videos, allow repetitions
            selected = random.choices(unique_backgrounds, k=count)
        
        logger.debug(f"Selected {len(selected)} background videos (requested {count})")
        return selected
    
    def get_video_metadata(self, video_path: Path) -> Dict[str, Any]:
        """
        Get metadata for a video file using ffprobe.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video metadata
        """
        # Check cache first
        if video_path in self._video_cache:
            return self._video_cache[video_path]
        
        try:
            # Use ffprobe to get video metadata
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Extract relevant metadata
            metadata = {
                'path': str(video_path),
                'exists': video_path.exists(),
                'size_bytes': video_path.stat().st_size if video_path.exists() else 0,
            }
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if video_stream:
                # Get dimensions
                width = int(video_stream.get('width', 0))
                height = int(video_stream.get('height', 0))
                
                # Get duration
                duration_str = data.get('format', {}).get('duration')
                if duration_str:
                    duration = float(duration_str)
                else:
                    # Try to get from video stream
                    duration = float(video_stream.get('duration', 0))
                
                # Get frame rate
                fps_str = video_stream.get('avg_frame_rate', '30/1')
                if '/' in fps_str:
                    num, den = map(int, fps_str.split('/'))
                    fps = num / den if den != 0 else 30.0
                else:
                    fps = float(fps_str)
                
                metadata.update({
                    'width': width,
                    'height': height,
                    'duration_seconds': duration,
                    'fps': fps,
                    'aspect_ratio': f"{width}:{height}",
                    'is_portrait': height > width,
                    'is_landscape': width > height,
                    'is_square': width == height,
                })
            
            # Cache the result
            self._video_cache[video_path] = metadata
            
            logger.debug(f"Video metadata for {video_path.name}: {metadata.get('width', 0)}x{metadata.get('height', 0)}, {metadata.get('duration_seconds', 0):.1f}s")
            
            return metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to get metadata for {video_path}: {e}")
            # Return basic metadata
            metadata = {
                'path': str(video_path),
                'exists': video_path.exists(),
                'size_bytes': video_path.stat().st_size if video_path.exists() else 0,
                'width': 0,
                'height': 0,
                'duration_seconds': 0,
                'fps': 30.0,
                'error': str(e),
            }
            self._video_cache[video_path] = metadata
            return metadata
    
    def is_video_916(self, video_path: Path) -> bool:
        """
        Check if a video is already in 9:16 aspect ratio (1080x1920).
        
        Args:
            video_path: Path to video file
            
        Returns:
            True if video is 9:16, False otherwise
        """
        metadata = self.get_video_metadata(video_path)
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        
        # Check for exact 9:16 ratio (1080x1920)
        if width == 1080 and height == 1920:
            return True
        
        # Check for approximate 9:16 ratio (within tolerance)
        if width > 0 and height > 0:
            aspect_ratio = width / height
            target_ratio = 9 / 16  # 0.5625
            tolerance = 0.05  # 5% tolerance
            
            return abs(aspect_ratio - target_ratio) < tolerance
        
        return False
    
    def get_random_start_time(self, video_path: Path, clip_duration: float) -> float:
        """
        Get a random start time for a video clip.
        
        Args:
            video_path: Path to video file
            clip_duration: Desired duration of the clip in seconds
            
        Returns:
            Random start time in seconds
        """
        metadata = self.get_video_metadata(video_path)
        video_duration = metadata.get('duration_seconds', 0)
        
        if video_duration <= clip_duration:
            # Video is shorter than or equal to desired clip duration
            return 0.0
        
        # Calculate maximum start time (video duration - clip duration)
        max_start = video_duration - clip_duration
        
        # Generate random start time
        start_time = random.uniform(0.0, max_start)
        
        logger.debug(f"Random start time for {clip_duration:.1f}s clip: {start_time:.1f}s (video duration: {video_duration:.1f}s)")
        
        return start_time
    
    def extract_video_clip(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        output_path: Path,
        target_width: int = 1080,
        target_height: int = 1920
    ) -> bool:
        """
        Extract a clip from a video and crop/scale it to 9:16.
        
        Args:
            video_path: Path to source video
            start_time: Start time in seconds
            duration: Clip duration in seconds
            output_path: Path where extracted clip will be saved
            target_width: Target width (default 1080)
            target_height: Target height (default 1920)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get video metadata
            metadata = self.get_video_metadata(video_path)
            original_width = metadata.get('width', 0)
            original_height = metadata.get('height', 0)
            
            if original_width == 0 or original_height == 0:
                logger.error(f"Cannot extract clip: Invalid video dimensions {original_width}x{original_height}")
                return False
            
            # Calculate crop parameters for 9:16 aspect ratio
            target_aspect = target_width / target_height  # 9/16 = 0.5625
            
            if original_width / original_height > target_aspect:
                # Video is wider than target aspect ratio, crop width
                crop_height = original_height
                crop_width = int(original_height * target_aspect)
            else:
                # Video is taller than target aspect ratio, crop height
                crop_width = original_width
                crop_height = int(original_width / target_aspect)
            
            # Center crop
            x_offset = max(0, (original_width - crop_width) // 2)
            y_offset = max(0, (original_height - crop_height) // 2)
            
            logger.info(f"Extracting clip: {start_time:.1f}s + {duration:.1f}s from {video_path.name}")
            logger.info(f"Original: {original_width}x{original_height}, Crop: {crop_width}x{crop_height}, Offset: ({x_offset}, {y_offset})")
            
            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-ss', str(start_time),  # Start time
                '-i', str(video_path),  # Input file
                '-t', str(duration),  # Duration
                '-filter_complex', f'[0:v]crop={crop_width}:{crop_height}:{x_offset}:{y_offset},scale={target_width}:{target_height}[v]',
                '-map', '[v]',  # Map video stream
                '-map', '0:a?',  # Map audio stream if exists
                '-c:v', 'libx264',  # Video codec
                '-preset', 'veryfast',  # Encoding speed
                '-crf', '23',  # Quality
                '-c:a', 'aac',  # Audio codec
                '-b:a', '128k',  # Audio bitrate
                '-movflags', '+faststart',  # Enable streaming
                str(output_path)
            ]
            
            # Run ffmpeg command
            logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg failed with error: {result.stderr}")
                return False
            
            # Verify output file
            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.error(f"Output file not created or empty: {output_path}")
                return False
            
            # Get output metadata
            output_metadata = self.get_video_metadata(output_path)
            output_duration = output_metadata.get('duration_seconds', 0)
            
            # Check if duration matches (within tolerance)
            duration_diff = abs(output_duration - duration)
            if duration_diff > 0.5:  # 500ms tolerance
                logger.warning(f"Output duration mismatch: expected {duration:.1f}s, got {output_duration:.1f}s")
            
            logger.info(f"Clip extracted successfully: {output_path} ({output_duration:.1f}s, {output_metadata.get('width', 0)}x{output_metadata.get('height', 0)})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to extract video clip: {e}")
            return False
    
    def create_background_clip(
        self,
        duration: float,
        theme: Optional[str] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Create a background video clip of specified duration.
        
        Args:
            duration: Desired clip duration in seconds
            theme: Optional theme for background selection
            output_path: Optional output path (defaults to temporary file)
            
        Returns:
            Path to created clip, or None if failed
        """
        # Validate duration
        if duration <= 0:
            logger.error(f"Invalid duration: {duration}")
            return None
        
        if duration > settings.MAX_BACKGROUND_DURATION:
            logger.warning(f"Duration {duration}s exceeds maximum {settings.MAX_BACKGROUND_DURATION}s, clipping")
            duration = min(duration, settings.MAX_BACKGROUND_DURATION)
        
        # Select background video
        background_path = self.get_random_background(theme)
        if not background_path:
            logger.error("No background videos available")
            return None
        
        # Get video metadata
        metadata = self.get_video_metadata(background_path)
        video_duration = metadata.get('duration_seconds', 0)
        
        if video_duration < duration:
            logger.warning(f"Background video ({video_duration:.1f}s) is shorter than requested duration ({duration:.1f}s)")
            # We'll use the entire video and loop if needed
            duration = video_duration
        
        # Create output path if not provided
        if output_path is None:
            import uuid
            temp_dir = Path(tempfile.gettempdir())
            output_path = temp_dir / f"background_{uuid.uuid4()}.mp4"
        
        # Get random start time
        start_time = self.get_random_start_time(background_path, duration)
        
        # Extract clip
        success = self.extract_video_clip(
            video_path=background_path,
            start_time=start_time,
            duration=duration,
            output_path=output_path,
            target_width=settings.TARGET_WIDTH,
            target_height=settings.TARGET_HEIGHT
        )
        
        if not success:
            logger.error(f"Failed to create background clip")
            return None
        
        return output_path
    
    def create_sequential_background_clip(
        self,
        duration: float,
        theme: Optional[str] = None,
        output_path: Optional[Path] = None,
        max_clip_duration: float = 10.0
    ) -> Optional[Path]:
        """
        Create a sequential background video clip by concatenating random clips
        from multiple background videos to cover the target duration.
        
        Args:
            duration: Desired total clip duration in seconds
            theme: Optional theme for background selection
            output_path: Optional output path (defaults to temporary file)
            max_clip_duration: Maximum duration for each individual clip (default 10s)
            
        Returns:
            Path to created sequential clip, or None if failed
        """
        import math
        import uuid
        import shutil
        
        # Validate duration
        if duration <= 0:
            logger.error(f"Invalid duration: {duration}")
            return None
        
        if duration > settings.MAX_BACKGROUND_DURATION:
            logger.warning(f"Duration {duration}s exceeds maximum {settings.MAX_BACKGROUND_DURATION}s, clipping")
            duration = min(duration, settings.MAX_BACKGROUND_DURATION)
        
        # Calculate number of clips needed
        num_clips = max(1, math.ceil(duration / max_clip_duration))
        logger.info(f"Creating sequential background clip: {duration:.1f}s total using {num_clips} clips")
        
        # Get random backgrounds
        backgrounds = self.get_random_backgrounds(num_clips, theme)
        if not backgrounds:
            logger.error("No background videos available")
            return None
        
        # Create temporary directory for intermediate clips
        temp_dir = Path(tempfile.mkdtemp())
        try:
            clip_paths = []
            accumulated_duration = 0.0
            
            for i, bg_path in enumerate(backgrounds):
                # Calculate clip duration for this segment
                remaining = duration - accumulated_duration
                if remaining <= 0:
                    break
                
                clip_duration = min(max_clip_duration, remaining)
                
                # Get video metadata to ensure we don't exceed source duration
                metadata = self.get_video_metadata(bg_path)
                source_duration = metadata.get('duration_seconds', 0)
                if source_duration < clip_duration:
                    # Source is shorter than desired clip duration, use entire video
                    clip_duration = source_duration
                
                if clip_duration <= 0:
                    logger.warning(f"Background video {bg_path.name} has zero duration, skipping")
                    continue
                
                # Generate random start time
                start_time = self.get_random_start_time(bg_path, clip_duration)
                
                # Create output path for this clip
                clip_path = temp_dir / f"clip_{i}_{uuid.uuid4().hex[:8]}.mp4"
                
                # Extract clip
                success = self.extract_video_clip(
                    video_path=bg_path,
                    start_time=start_time,
                    duration=clip_duration,
                    output_path=clip_path,
                    target_width=settings.TARGET_WIDTH,
                    target_height=settings.TARGET_HEIGHT
                )
                
                if not success:
                    logger.error(f"Failed to extract clip {i} from {bg_path.name}")
                    continue
                
                # Verify clip was created and has content
                if not clip_path.exists() or clip_path.stat().st_size == 0:
                    logger.error(f"Extracted clip {i} is empty or missing: {clip_path}")
                    continue
                
                clip_paths.append(clip_path)
                accumulated_duration += clip_duration
                
                logger.debug(f"Created clip {i+1}/{num_clips}: {clip_duration:.1f}s from {bg_path.name}")
                
                if accumulated_duration >= duration:
                    break
            
            if not clip_paths:
                logger.error("No clips were successfully extracted")
                return None
            
            if accumulated_duration < duration:
                logger.warning(f"Accumulated duration ({accumulated_duration:.1f}s) is less than requested ({duration:.1f}s)")
            
            # Create output path if not provided
            if output_path is None:
                output_path = Path(tempfile.gettempdir()) / f"sequential_background_{uuid.uuid4()}.mp4"
            
            # Create concat file list
            concat_file = temp_dir / "concat_list.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                for clip_path in clip_paths:
                    # Escape single quotes and backslashes for Windows paths
                    path_str = str(clip_path).replace('\\', '\\\\').replace("'", "'\\''")
                    f.write(f"file '{path_str}'\n")
            
            # Use FFmpeg concat demuxer to concatenate clips
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # Copy codec (fast, no re-encoding)
                '-movflags', '+faststart',
                str(output_path)
            ]
            
            logger.info(f"Concatenating {len(clip_paths)} clips into sequential background")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg concatenation failed: {result.stderr}")
                return None
            
            # Verify output file
            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.error(f"Output file not created or empty: {output_path}")
                return None
            
            # Get output metadata
            output_metadata = self.get_video_metadata(output_path)
            output_duration = output_metadata.get('duration_seconds', 0)
            
            # Check if duration matches (within tolerance)
            duration_diff = abs(output_duration - accumulated_duration)
            if duration_diff > 1.0:  # 1 second tolerance
                logger.warning(f"Output duration mismatch: expected {accumulated_duration:.1f}s, got {output_duration:.1f}s")
            
            logger.info(f"Sequential background clip created: {output_path} ({output_duration:.1f}s, {len(clip_paths)} clips)")
            return output_path
            
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

    def validate_backgrounds(self) -> Dict[str, Any]:
        """
        Validate all background videos in the backgrounds directory.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'total_backgrounds': 0,
            'valid_backgrounds': 0,
            'invalid_backgrounds': 0,
            'themes': {},
            'errors': []
        }
        
        for theme in self.get_available_themes():
            theme_results = {
                'total': 0,
                'valid': 0,
                'invalid': 0,
                'videos': []
            }
            
            backgrounds = self.get_backgrounds_by_theme(theme)
            results['total_backgrounds'] += len(backgrounds)
            theme_results['total'] = len(backgrounds)
            
            for bg_path in backgrounds:
                video_info = {
                    'path': str(bg_path),
                    'name': bg_path.name,
                }
                
                try:
                    metadata = self.get_video_metadata(bg_path)
                    
                    # Check if video is valid
                    if metadata.get('width', 0) > 0 and metadata.get('height', 0) > 0:
                        video_info.update({
                            'width': metadata['width'],
                            'height': metadata['height'],
                            'duration': metadata['duration_seconds'],
                            'fps': metadata['fps'],
                            'is_916': self.is_video_916(bg_path),
                            'valid': True
                        })
                        
                        results['valid_backgrounds'] += 1
                        theme_results['valid'] += 1
                    else:
                        video_info['valid'] = False
                        video_info['error'] = 'Invalid dimensions'
                        
                        results['invalid_backgrounds'] += 1
                        theme_results['invalid'] += 1
                        results['errors'].append(f"Invalid video: {bg_path.name}")
                        
                except Exception as e:
                    video_info['valid'] = False
                    video_info['error'] = str(e)
                    
                    results['invalid_backgrounds'] += 1
                    theme_results['invalid'] += 1
                    results['errors'].append(f"Error processing {bg_path.name}: {e}")
                
                theme_results['videos'].append(video_info)
            
            results['themes'][theme] = theme_results
        
        return results


# Utility functions for direct use
def create_background_clip(
    duration: float,
    theme: Optional[str] = None,
    output_path: Optional[Path] = None
) -> Optional[Path]:
    """
    Convenience function to create a background clip.
    
    Args:
        duration: Desired clip duration in seconds
        theme: Optional theme for background selection
        output_path: Optional output path
        
    Returns:
        Path to created clip, or None if failed
    """
    manager = BackgroundManager()
    return manager.create_background_clip(duration, theme, output_path)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def example():
        # Create background manager
        manager = BackgroundManager()
        
        # Get available themes
        themes = manager.get_available_themes()
        print(f"Available themes: {themes}")
        
        # Validate backgrounds
        print("\nValidating backgrounds...")
        validation = manager.validate_backgrounds()
        print(f"Total backgrounds: {validation['total_backgrounds']}")
        print(f"Valid backgrounds: {validation['valid_backgrounds']}")
        print(f"Invalid backgrounds: {validation['invalid_backgrounds']}")
        
        # Create a test background clip
        print("\nCreating test background clip...")
        clip_path = manager.create_background_clip(
            duration=10.0,  # 10 second clip
            theme="minecraft" if "minecraft" in themes else None
        )
        
        if clip_path:
            print(f"Created background clip: {clip_path}")
            
            # Get metadata
            metadata = manager.get_video_metadata(clip_path)
            print(f"Clip dimensions: {metadata.get('width', 0)}x{metadata.get('height', 0)}")
            print(f"Clip duration: {metadata.get('duration_seconds', 0):.1f}s")
            print(f"Is 9:16: {manager.is_video_916(clip_path)}")
            
            # Clean up
            clip_path.unlink()
            print("Test clip cleaned up")
        else:
            print("Failed to create background clip")
        
        print("\nExample completed successfully!")
    
    # Run example
    asyncio.run(example())
