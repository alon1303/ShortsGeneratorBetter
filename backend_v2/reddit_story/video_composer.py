"""
Video Composer for Reddit Stories Shorts.
Combines audio narration with background videos and adds Shorts-style subtitles.
"""

import logging
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import uuid

from config.settings import settings
from .background_manager import BackgroundManager
from .models import AudioChunk, WordTimestamp
from .subtitle_generator import SubtitleGenerator
from .audio_utils import adjust_word_timestamps, detect_silence_at_beginning
from .image_generator_new import TitlePopupTimingCalculator
from .audio_mixer import AudioMixer

# Configure logging
logger = logging.getLogger(__name__)

class VideoComposer:
    """Composes Shorts videos by combining audio, background, and subtitles."""
    
    def __init__(self, background_manager: Optional[BackgroundManager] = None):
        self.background_manager = background_manager or BackgroundManager()
        self.audio_mixer = AudioMixer()
        logger.info("VideoComposer initialized")
    
    def _validate_background_fps(self, background_path: Path) -> bool:
        try:
            metadata = self.background_manager.get_video_metadata(background_path)
            background_fps = metadata.get('fps', 0)
            target_fps = settings.TARGET_FPS
            if background_fps <= 0:
                return False
            tolerance = 0.5
            fps_match = abs(background_fps - target_fps) <= tolerance
            return fps_match
        except Exception as e:
            logger.error(f"Failed to validate background FPS: {e}")
            return False
    
    def create_subtitles_for_text(
        self,
        text: str,
        audio_duration: float,
        output_path: Path,
        word_timestamps: Optional[List[WordTimestamp]] = None,
        audio_path: Optional[Path] = None,
        title_offset: float = 0.0,
        title_word_count: int = 0,
        is_first_part: bool = False,
        timing_data: Optional[Dict[str, Any]] = None
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
                min_start_time = 0.0
                if timing_data and 'card_end_time' in timing_data:
                    min_start_time = float(timing_data['card_end_time'])
                
                success, _ = generator.generate_ass_with_title_filter(
                    word_timestamps=adjusted_word_timestamps,
                    title_word_count=title_word_count,
                    audio_duration=audio_duration,
                    output_path=output_path,
                    min_start_time=min_start_time
                )
                return success
            else:
                if title_offset > 0 and adjusted_word_timestamps:
                    adjusted_word_timestamps = adjust_word_timestamps(adjusted_word_timestamps, title_offset)
                
                success = generator.generate_ass_with_pysubs2(
                    word_timestamps=adjusted_word_timestamps,
                    audio_duration=audio_duration + title_offset,
                    output_path=output_path,
                    min_start_time=0.0
                )
                return success
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
        bg_music_path: Optional[Path] = None,
        timing_data: Optional[Dict[str, Any]] = None,
        hook_duration: Optional[float] = None
    ) -> bool:
        try:
            self._validate_background_fps(background_path)
            
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
            
            if pop_sfx_temp and pop_sfx_temp.exists():
                mixed_audio_path = self.audio_mixer.mix_title_with_pop_sfx(
                    main_audio_path=audio_temp,
                    pop_sfx_path=pop_sfx_temp,
                    pop_start_time=0.6,
                    pop_volume_delta=-6.0,
                    output_path=temp_path / "audio_mixed.mp3"
                )
                if mixed_audio_path and mixed_audio_path.exists():
                    current_audio_path = mixed_audio_path
            
            if bg_music_path and bg_music_path.exists():
                bgm_temp = temp_path / bg_music_path.name
                shutil.copy2(bg_music_path, bgm_temp)
                mixed_with_bgm_path = self.audio_mixer.add_background_music(
                    main_audio_path=current_audio_path,
                    bg_music_path=bgm_temp,
                    output_path=temp_path / "audio_fully_mixed.mp3",
                    bg_volume_delta=settings.BGM_VOLUME_DELTA,
                )
                if mixed_with_bgm_path and mixed_with_bgm_path.exists():
                    current_audio_path = mixed_with_bgm_path

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
                        calculator = TitlePopupTimingCalculator(
                            title_audio_duration=timing_data['title_audio_duration'],
                            buffer_seconds=timing_data['buffer_seconds']
                        )
                        filter_complex = calculator.get_ffmpeg_filter_for_animation(overlay_temp, card_end_time=card_end)
                    else:
                        filter_complex = (
                            f'[1:v]scale=900:-1[overlay_scaled];'
                            f'[0:v][overlay_scaled]overlay=x=(W-w)/2:y=(H-h)/2:enable=\'between(t,{card_start},{card_end})\''
                        )
                else:
                    card_start = 0.0
                    card_end = hook_duration if hook_duration is not None and hook_duration > 0 else 4.0
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
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-t', str(audio_duration), '-movflags', '+faststart',
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
            return output_path.exists() and output_path.stat().st_size > 0
            
        except Exception as e:
            logger.error(f"Failed to combine audio with background: {e}")
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return False
    
    def apply_speed_multiplier(self, input_path: Path, output_path: Path, speed_multiplier: float) -> bool:
        try:
            pts_value = 1.0 / speed_multiplier
            cmd = [
                'ffmpeg', '-y', '-i', str(input_path),
                '-filter_complex', f'[0:v]setpts={pts_value:.4f}*PTS[v];[0:a]atempo={speed_multiplier}[a]',
                '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
        except Exception:
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
        bg_music_path: Optional[Path] = None,
        dynamic_switching: Optional[bool] = None
    ) -> Optional[Path]:
        if not audio_chunk.audio_path.exists():
            return None
        
        if output_path is None:
            output_path = Path(tempfile.gettempdir()) / f"video_part_{uuid.uuid4()}.mp4"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            use_dynamic = dynamic_switching if dynamic_switching is not None else settings.BACKGROUND_DYNAMIC_SWITCHING
            background_path = self.background_manager.create_sequential_background_clip(
                duration=audio_chunk.duration_seconds,
                theme=theme,
                output_path=temp_path / "background.mp4",
                dynamic_switching=use_dynamic
            )
            if not background_path:
                return None
            
            subtitle_path = temp_path / "subtitles.ass"
            title_offset = timing_data.get('subtitle_start_time', 0.0) if timing_data else 0.0
            title_word_count = timing_data.get('title_word_count', 0) if timing_data else 0
            
            self.create_subtitles_for_text(
                text=audio_chunk.text,
                audio_duration=audio_chunk.duration_seconds,
                output_path=subtitle_path,
                word_timestamps=audio_chunk.word_timestamps,
                audio_path=audio_chunk.audio_path,
                title_offset=title_offset,
                title_word_count=title_word_count,
                is_first_part=audio_chunk.is_first_part,
                timing_data=timing_data
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
                bg_music_path=bg_music_path
            )
            if not success:
                return None
        
        speed = getattr(settings, 'FINAL_VIDEO_SPEED', 1.4)
        if speed != 1.0:
            final_path = output_path.parent / f"{output_path.stem}_{speed}x{output_path.suffix}"
            if self.apply_speed_multiplier(output_path, final_path, speed):
                return final_path
        return output_path
    
    def concatenate_videos(self, video_paths: List[Path], output_path: Path) -> bool:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for vp in video_paths:
                    if vp.exists():
                        f.write(f"file '{str(vp).replace('\\', '\\\\')}'\n")
                filelist = Path(f.name)
            try:
                cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(filelist),
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0 and output_path.exists()
            finally:
                filelist.unlink()
        except Exception:
            return False
    
    def create_complete_shorts_video(
        self,
        audio_chunks: List[AudioChunk],
        theme: Optional[str] = None,
        output_path: Optional[Path] = None,
        overlay_image_path: Optional[Path] = None,
        pop_sfx_path: Optional[Path] = None,
        bg_music_path: Optional[Path] = None
    ) -> Path:
        if output_path is None:
            output_path = settings.OUTPUT_DIR / f"shorts_{uuid.uuid4()}.mp4"
        
        video_parts = []
        for i, chunk in enumerate(audio_chunks, 1):
            part = self.create_video_part(
                audio_chunk=chunk, theme=theme,
                overlay_image_path=overlay_image_path if i == 1 else None,
                pop_sfx_path=pop_sfx_path if i == 1 else None,
                bg_music_path=bg_music_path
            )
            if part:
                video_parts.append(part)
        
        if len(video_parts) == 1:
            shutil.copy2(video_parts[0], output_path)
        else:
            self.concatenate_videos(video_parts, output_path)
        return output_path

def create_shorts_video(audio_chunks, theme=None, output_path=None, overlay_image_path=None, pop_sfx_path=None, bg_music_path=None):
    return VideoComposer().create_complete_shorts_video(audio_chunks, theme, output_path, overlay_image_path, pop_sfx_path, bg_music_path)
