"""
Video Composer for Reddit Stories Shorts.
Combines audio narration with background videos and adds Shorts-style subtitles.
"""

import logging
import tempfile
import subprocess
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import uuid

from config.settings import settings
from .background_manager import BackgroundManager
from .models import AudioChunk, WordTimestamp
from .subtitle_generator import SubtitleGenerator, generate_subtitles
from .audio_utils import analyze_audio_for_offset, adjust_word_timestamps, detect_silence_at_beginning
from .image_generator_new import TitlePopupTimingCalculator, RedditImageGenerator
from .audio_mixer import AudioMixer

# Configure logging
logger = logging.getLogger(__name__)

class VideoComposer:
    """Composes Shorts videos by combining audio, background, and subtitles."""
    
    def __init__(self, background_manager: Optional[BackgroundManager] = None):
        self.background_manager = background_manager or BackgroundManager()
        self.audio_mixer = AudioMixer()
        logger.info("VideoComposer initialized")
    
    def create_subtitles_for_text(
        self,
        text: str,
        audio_duration: float,
        output_path: Path,
        word_timestamps: Optional[List[WordTimestamp]] = None,
        audio_path: Optional[Path] = None,
        title_offset: float = 0.0,
        title_word_count: int = 0
    ) -> bool:
        generator = SubtitleGenerator(
            video_width=1080,
            video_height=1920,
            max_words_per_phrase=5,
            min_words_per_phrase=2,
            max_phrase_duration=3.0,
            min_gap_between_phrases=0.1
        )
        
        adjusted_word_timestamps = word_timestamps
        if audio_path and audio_path.exists() and word_timestamps:
            silence_offset = detect_silence_at_beginning(audio_path)
            if silence_offset > 0.05:
                adjusted_word_timestamps = adjust_word_timestamps(word_timestamps, -silence_offset)
        
        if adjusted_word_timestamps:
            if title_word_count > 0:
                success, _ = generator.generate_ass_with_title_filter(
                    word_timestamps=adjusted_word_timestamps,
                    title_word_count=title_word_count,
                    audio_duration=audio_duration + title_offset,
                    output_path=output_path
                )
                if not success:
                    raise RuntimeError("Failed to generate subtitles with title filter")
                return True
            else:
                if title_offset > 0 and adjusted_word_timestamps:
                    adjusted_word_timestamps = adjust_word_timestamps(adjusted_word_timestamps, title_offset)
                
                success = generator.generate_ass_from_word_timestamps(
                    word_timestamps=adjusted_word_timestamps,
                    audio_duration=audio_duration + title_offset,
                    output_path=output_path
                )
                if not success:
                    raise RuntimeError("Failed to generate subtitles from word timestamps")
                return True
        else:
            return generator.generate_ass_from_text(
                text=text,
                audio_duration=audio_duration + title_offset,
                output_path=output_path
            )
    
    def combine_audio_with_background(
        self,
        audio_path: Path,
        background_path: Path,
        output_path: Path,
        subtitle_path: Optional[Path] = None,
        overlay_image_path: Optional[Path] = None,
        pop_sfx_path: Optional[Path] = None,
        bg_music_path: Optional[Path] = None,  # Added bg_music_path
        timing_data: Optional[Dict[str, Any]] = None,
        hook_duration: Optional[float] = None
    ) -> bool:
        try:
            audio_cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)
            ]
            audio_result = subprocess.run(audio_cmd, capture_output=True, text=True)
            audio_duration = float(audio_result.stdout.strip()) if audio_result.stdout else 0
            
            if audio_duration <= 0:
                return False
            
            temp_dir = tempfile.mkdtemp()
            temp_path = Path(temp_dir)
            
            audio_temp = temp_path / audio_path.name
            shutil.copy2(audio_path, audio_temp)
            
            background_temp = temp_path / background_path.name
            shutil.copy2(background_path, background_temp)
            
            overlay_temp = None
            if overlay_image_path and overlay_image_path.exists():
                overlay_temp = temp_path / overlay_image_path.name
                shutil.copy2(overlay_image_path, overlay_temp)
            
            pop_sfx_temp = None
            if pop_sfx_path and pop_sfx_path.exists():
                pop_sfx_temp = temp_path / pop_sfx_path.name
                shutil.copy2(pop_sfx_path, pop_sfx_temp)
            
            subtitle_temp = None
            if subtitle_path and subtitle_path.exists():
                subtitle_temp = temp_path / subtitle_path.name
                shutil.copy2(subtitle_path, subtitle_temp)
            
            current_audio_path = audio_temp
            
            # Mix pop SFX
            if pop_sfx_temp and pop_sfx_temp.exists():
                mixed_audio_path = self.audio_mixer.mix_title_with_pop_sfx(
                    main_audio_path=audio_temp,
                    pop_sfx_path=pop_sfx_temp,
                    pop_start_time=0.0,
                    pop_volume_delta=-6.0,
                    output_path=temp_path / "audio_mixed.mp3"
                )
                if mixed_audio_path and mixed_audio_path.exists():
                    current_audio_path = mixed_audio_path
            
            # Mix LoFi Background Music
            if bg_music_path and bg_music_path.exists():
                logger.info(f"Adding background music using AudioMixer: {bg_music_path.name}")
                bgm_temp = temp_path / bg_music_path.name
                shutil.copy2(bg_music_path, bgm_temp)
                
                mixed_with_bgm_path = self.audio_mixer.add_background_music(
                    main_audio_path=current_audio_path,
                    bg_music_path=bgm_temp,
                    output_path=temp_path / "audio_fully_mixed.mp3",
                    bg_volume_delta=0.0,  # You can adjust this if needed
                )
                
                if mixed_with_bgm_path and mixed_with_bgm_path.exists():
                    current_audio_path = mixed_with_bgm_path
                    logger.info("Background music mixed successfully")

            cmd = ['ffmpeg', '-y']
            cmd.extend(['-i', background_temp.name])
            
            if overlay_temp and overlay_temp.exists():
                cmd.extend(['-loop', '1', '-framerate', '30', '-i', overlay_temp.name])
            
            cmd.extend(['-i', current_audio_path.name])
            
            filter_complex = None
            if overlay_temp and overlay_temp.exists():
                if timing_data and 'card_start_time' in timing_data and 'card_end_time' in timing_data:
                    card_start = timing_data['card_start_time']
                    card_end = timing_data['card_end_time']
                    
                    if ('title_audio_duration' in timing_data and 'buffer_seconds' in timing_data and
                        'pop_in_duration' in timing_data):
                        visual_gap = 0.15
                        adjusted_duration = max(0.5, timing_data['title_audio_duration'] - visual_gap)
                        calculator = TitlePopupTimingCalculator(
                            title_audio_duration=adjusted_duration,
                            buffer_seconds=timing_data['buffer_seconds']
                        )
                        filter_complex = calculator.get_ffmpeg_filter_for_animation(overlay_temp)
                    else:
                        visual_gap = 0.15
                        adjusted_card_end = max(0.5, card_end - visual_gap)
                        filter_complex = (
                            f'[1:v]scale=900:-1[overlay_scaled];'
                            f'[0:v][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:enable=\'between(t,{card_start},{adjusted_card_end})\''
                        )
                else:
                    card_start = 0.0
                    if hook_duration is not None and hook_duration > 0:
                        card_end = hook_duration
                    else:
                        card_end = 4.0
                    filter_complex = (
                        f'[1:v]scale=900:-1[overlay_scaled];'
                        f'[0:v][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:enable=\'between(t,{card_start},{card_end})\''
                    )
            
            if subtitle_temp and subtitle_temp.exists():
                if filter_complex:
                    filter_complex += f',subtitles={subtitle_temp.name}[vout]'
                else:
                    filter_complex = f'[0:v]subtitles={subtitle_temp.name}[vout]'
            elif filter_complex:
                filter_complex += '[vout]'
            
            if filter_complex:
                cmd.extend(['-filter_complex', filter_complex])
                cmd.extend(['-map', '[vout]'])
            else:
                cmd.extend(['-map', '0:v'])
            
            if overlay_temp and overlay_temp.exists():
                cmd.extend(['-map', '2:a'])
            else:
                cmd.extend(['-map', '1:a'])
            
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-t', str(audio_duration),
                '-movflags', '+faststart',
                output_path.name
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_path)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg failed: {result.stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            output_temp = temp_path / output_path.name
            if output_temp.exists():
                shutil.copy2(output_temp, output_path)
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to combine audio with background: {e}")
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return False
    
    def apply_speed_multiplier(self, input_path: Path, output_path: Path, speed_multiplier: float) -> bool:
        try:
            pts_value = 1.0 / speed_multiplier
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-filter_complex', f'[0:v]setpts={pts_value:.4f}*PTS[v];[0:a]atempo={speed_multiplier}[a]',
                '-map', '[v]', '-map', '[a]',
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-c:a', 'aac',
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False
            if not output_path.exists() or output_path.stat().st_size == 0:
                return False
            return True
        except Exception as e:
            return False

    def create_video_part(
        self,
        audio_chunk: AudioChunk,
        theme: Optional[str] = None,
        output_path: Optional[Path] = None,
        overlay_image_path: Optional[Path] = None,
        pop_sfx_path: Optional[Path] = None,
        timing_data: Optional[Dict[str, Any]] = None,
        hook_duration: Optional[float] = None,
        bg_music_path: Optional[Path] = None  # Added bg_music_path
    ) -> Optional[Path]:
        if not audio_chunk.audio_path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {audio_chunk.audio_path}")
        if audio_chunk.duration_seconds <= 0:
            raise ValueError(f"Invalid audio duration: {audio_chunk.duration_seconds}")
        
        if output_path is None:
            temp_dir = Path(tempfile.gettempdir())
            output_path = temp_dir / f"video_part_{uuid.uuid4()}.mp4"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            logger.info(f"Creating sequential background clip for {audio_chunk.duration_seconds:.1f}s audio")
            background_path = self.background_manager.create_sequential_background_clip(
                duration=audio_chunk.duration_seconds,
                theme=theme,
                output_path=temp_path / "background.mp4"
            )
            
            if not background_path:
                raise RuntimeError("Failed to create background clip")
            
            subtitle_path = temp_path / "subtitles.ass"
            
            title_offset = 0.0
            title_word_count = 0
            if timing_data:
                if 'subtitle_start_time' in timing_data:
                    title_offset = timing_data['subtitle_start_time']
                if 'title_word_count' in timing_data:
                    title_word_count = timing_data['title_word_count']
            
            self.create_subtitles_for_text(
                text=audio_chunk.text,
                audio_duration=audio_chunk.duration_seconds,
                output_path=subtitle_path,
                word_timestamps=audio_chunk.word_timestamps,
                audio_path=audio_chunk.audio_path,
                title_offset=title_offset,
                title_word_count=title_word_count
            )
            
            success = self.combine_audio_with_background(
                audio_path=audio_chunk.audio_path,
                background_path=background_path,
                output_path=output_path,
                subtitle_path=subtitle_path,
                overlay_image_path=overlay_image_path,
                pop_sfx_path=pop_sfx_path,
                timing_data=timing_data,
                hook_duration=hook_duration,
                bg_music_path=bg_music_path  # Pass bg_music_path
            )
            
            if not success:
                raise RuntimeError("Failed to combine audio with background")
        
        speed_multiplier = getattr(settings, 'FINAL_VIDEO_SPEED', 1.4)
        if speed_multiplier != 1.0:
            final_speed_path = output_path.parent / f"{output_path.stem}_{speed_multiplier}x{output_path.suffix}"
            speed_success = self.apply_speed_multiplier(output_path, final_speed_path, speed_multiplier)
            if speed_success and final_speed_path.exists() and final_speed_path.stat().st_size > 0:
                final_return_path = final_speed_path
            else:
                final_return_path = output_path
        else:
            final_return_path = output_path
            
        return final_return_path
    
    def concatenate_videos(self, video_paths: List[Path], output_path: Path) -> bool:
        try:
            if not video_paths:
                return False
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for video_path in video_paths:
                    if video_path.exists():
                        path_str = str(video_path).replace('\\', '\\\\').replace("'", "'\\''")
                        f.write(f"file '{path_str}'\n")
                filelist_path = Path(f.name)
            
            try:
                cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(filelist_path),
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    return False
                if not output_path.exists() or output_path.stat().st_size == 0:
                    return False
                return True
            finally:
                filelist_path.unlink()
        except Exception as e:
            return False
    
    def create_complete_shorts_video(
        self,
        audio_chunks: List[AudioChunk],
        theme: Optional[str] = None,
        output_path: Optional[Path] = None,
        overlay_image_path: Optional[Path] = None,
        pop_sfx_path: Optional[Path] = None,
        bg_music_path: Optional[Path] = None  # Added bg_music_path
    ) -> Path:
        if not audio_chunks:
            raise ValueError("No audio chunks provided")
        
        if output_path is None:
            output_dir = settings.OUTPUT_DIR / "reddit_stories"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"shorts_{uuid.uuid4()}.mp4"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_parts = []
            
            for i, audio_chunk in enumerate(audio_chunks, 1):
                if audio_chunk.duration_seconds <= 0:
                    continue
                
                part_path = temp_path / f"part_{i}_{uuid.uuid4().hex[:8]}.mp4"
                video_part = self.create_video_part(
                    audio_chunk=audio_chunk,
                    theme=theme,
                    output_path=part_path,
                    overlay_image_path=overlay_image_path if i == 1 else None,
                    pop_sfx_path=pop_sfx_path if i == 1 else None,
                    bg_music_path=bg_music_path  # Pass bg_music_path
                )
                video_parts.append(video_part)
            
            if not video_parts:
                raise RuntimeError("No video parts were created successfully")
            
            if len(video_parts) == 1:
                shutil.copy2(video_parts[0], output_path)
            else:
                success = self.concatenate_videos(video_parts, output_path)
                if not success:
                    raise RuntimeError("Failed to concatenate video parts")
            
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"Final video not created: {output_path}")

            return output_path
    
    def create_separate_video_parts(
        self,
        audio_chunks: List[AudioChunk],
        output_dir: Path,
        theme: Optional[str] = None,
        overlay_image_path: Optional[Path] = None,
        pop_sfx_path: Optional[Path] = None,
        bg_music_path: Optional[Path] = None
    ) -> List[Path]:
        if not audio_chunks:
            raise ValueError("No audio chunks provided")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        video_parts = []
        
        for i, audio_chunk in enumerate(audio_chunks, 1):
            if audio_chunk.duration_seconds <= 0:
                continue
            
            part_filename = f"part_{i}_{uuid.uuid4().hex[:8]}.mp4"
            part_path = output_dir / part_filename
            
            video_part = self.create_video_part(
                audio_chunk=audio_chunk,
                theme=theme,
                output_path=part_path,
                overlay_image_path=overlay_image_path if i == 1 else None,
                pop_sfx_path=pop_sfx_path if i == 1 else None,
                bg_music_path=bg_music_path
            )
            video_parts.append(video_part)
        
        return video_parts


def create_shorts_video(
    audio_chunks: List[AudioChunk],
    theme: Optional[str] = None,
    output_path: Optional[Path] = None,
    overlay_image_path: Optional[Path] = None,
    pop_sfx_path: Optional[Path] = None,
    bg_music_path: Optional[Path] = None  # Added bg_music_path
) -> Path:
    """
    Convenience function to create a Shorts video from audio chunks.
    """
    composer = VideoComposer()
    return composer.create_complete_shorts_video(
        audio_chunks, 
        theme, 
        output_path,
        overlay_image_path,
        pop_sfx_path,
        bg_music_path  # Pass bg_music_path
    )