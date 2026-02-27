"""
TTS Router/Factory for Edge TTS engine.
Routes requests to the Edge TTS client.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from config.settings import settings
from .models import WordTimestamp, AudioChunk
from .edgetts_client import EdgeTTSClient
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import subprocess
import tempfile
import shutil

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class TTSConfig:
    """Configuration for TTS engine selection."""
    engine: str  # "edge"
    voice_id: Optional[str] = None
    cache_dir: Optional[Path] = None
    use_cache: bool = True
    
    @classmethod
    def from_settings(cls, voice_id: Optional[str] = None, cache_dir: Optional[Path] = None):
        """Create TTSConfig from application settings."""
        return cls(
            engine="edge",  # Only Edge TTS is supported
            voice_id=voice_id,
            cache_dir=cache_dir,
            use_cache=settings.ENABLE_CACHE
        )


class TTSRouter:
    """
    Router that selects the appropriate TTS client based on configuration.
    Provides a unified interface for Edge TTS.
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize TTS router.
        
        Args:
            config: TTS configuration (defaults to from_settings)
        """
        self.config = config or TTSConfig.from_settings()
        self._client = None
        
        logger.info(f"TTSRouter initialized with engine: {self.config.engine}")
    
    async def _get_client(self):
        """Get or create the appropriate TTS client."""
        if self._client is None:
            if self.config.engine == "edge":
                self._client = EdgeTTSClient(
                    voice=self.config.voice_id,
                    cache_dir=self.config.cache_dir
                )
            else:
                raise ValueError(f"Unknown TTS engine: {self.config.engine}. Use 'edge' only")
        
        return self._client
    
    async def text_to_speech_with_timestamps(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[Path], float, Optional[List[WordTimestamp]]]:
        """
        Convert text to speech with word-level timestamps.
        
        Args:
            text: Text to convert to speech
            voice: Voice ID to use (overrides config)
            **kwargs: Additional arguments passed to the client
            
        Returns:
            Tuple of (audio_file_path, duration_seconds, word_timestamps)
            Raises exception on error (fail-fast)
        """
        client = await self._get_client()
        
        # Use provided voice or config voice
        if voice is None and self.config.voice_id:
            voice = self.config.voice_id
        
        logger.debug(f"Routing TTS request to {self.config.engine} engine: {len(text)} chars")
        
        # Remove 'use_cache' from kwargs if present (we pass it explicitly)
        kwargs_without_use_cache = {k: v for k, v in kwargs.items() if k != 'use_cache'}
        
        if self.config.engine == "edge":
            return await client.text_to_speech_with_timestamps(
                text=text,
                voice=voice,
                use_cache=self.config.use_cache,
                **kwargs_without_use_cache,
            )
        else:
            raise ValueError(f"Unknown TTS engine: {self.config.engine}")
    
    async def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[Path], float]:
        """
        Convert text to speech (without timestamps).
        
        Args:
            text: Text to convert to speech
            voice: Voice ID to use (overrides config)
            **kwargs: Additional arguments passed to the client
            
        Returns:
            Tuple of (audio_file_path, duration_seconds)
            Raises exception on error (fail-fast)
        """
        client = await self._get_client()
        
        # Use provided voice or config voice
        if voice is None and self.config.voice_id:
            voice = self.config.voice_id
        
        logger.debug(f"Routing TTS request to {self.config.engine} engine: {len(text)} chars")
        
        if self.config.engine == "edge":
            return await client.text_to_speech(
                text=text,
                voice=voice,
                use_cache=self.config.use_cache,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown TTS engine: {self.config.engine}")
    
    async def generate_audio_chunks(
        self,
        text_chunks: List[str],
        voice: Optional[str] = None,
        with_timestamps: bool = True,
        **kwargs,
    ) -> List[AudioChunk]:
        """
        Generate audio for multiple text chunks.
        
        Args:
            text_chunks: List of text chunks to convert
            voice: Voice ID to use (overrides config)
            with_timestamps: Whether to request word-level timestamps
            **kwargs: Additional arguments passed to the client
            
        Returns:
            List of AudioChunk objects
        """
        client = await self._get_client()
        
        # Use provided voice or config voice
        if voice is None and self.config.voice_id:
            voice = self.config.voice_id
        
        logger.info(f"Routing audio generation to {self.config.engine} engine: {len(text_chunks)} chunks")
        
        if self.config.engine == "edge":
            return await client.generate_audio_chunks(
                text_chunks=text_chunks,
                voice=voice,
                with_timestamps=with_timestamps,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown TTS engine: {self.config.engine}")
    
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Get list of available voices for the configured engine.
        
        Returns:
            List of voice information dictionaries
        """
        client = await self._get_client()
        return await client.get_available_voices()
    
    async def close(self):
        """Close the TTS client connection."""
        if self._client:
            # EdgeTTS doesn't have persistent connections to close
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Factory functions for direct use
async def get_tts_client(
    engine: Optional[str] = None,
    voice: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    use_cache: Optional[bool] = None,
) -> TTSRouter:
    """
    Factory function to get a TTS router/client.
    
    Args:
        engine: TTS engine ("edge"), defaults to settings.TTS_ENGINE
        voice: Voice ID to use
        cache_dir: Cache directory
        use_cache: Whether to use caching
        
    Returns:
        TTSRouter instance
    """
    config = TTSConfig(
        engine=engine or settings.TTS_ENGINE.lower(),
        voice_id=voice,
        cache_dir=cache_dir,
        use_cache=use_cache if use_cache is not None else settings.ENABLE_CACHE
    )
    
    return TTSRouter(config)


async def generate_story_audio(
    text_chunks: List[str],
    voice: Optional[str] = None,
    with_timestamps: bool = True,
    engine: Optional[str] = None,
    **kwargs,
) -> List[AudioChunk]:
    """
    Convenience function to generate audio for story chunks.
    Automatically selects the appropriate TTS engine based on configuration.
    
    Args:
        text_chunks: List of text chunks to convert
        voice: Voice ID to use
        with_timestamps: Whether to request word-level timestamps
        engine: Override TTS engine ("edge")
        **kwargs: Additional arguments for TTSRouter
        
    Returns:
        List of AudioChunk objects
    """
    async with await get_tts_client(engine=engine, voice=voice) as router:
        return await router.generate_audio_chunks(
            text_chunks=text_chunks,
            voice=voice,
            with_timestamps=with_timestamps,
            **kwargs,
        )


# Utility function for backward compatibility
async def generate_story_audio_compat(
    text_chunks: List[str],
    voice_id: Optional[str] = None,
    with_timestamps: bool = True,
    **kwargs,
) -> List[AudioChunk]:
    """
    Backward compatibility wrapper for existing code.
    Uses "voice_id" parameter name for compatibility.
    
    Args:
        text_chunks: List of text chunks to convert
        voice_id: Voice ID to use
        with_timestamps: Whether to request word-level timestamps
        **kwargs: Additional arguments for TTSRouter
        
    Returns:
        List of AudioChunk objects
    """
    return await generate_story_audio(
        text_chunks=text_chunks,
        voice=voice_id,
        with_timestamps=with_timestamps,
        **kwargs,
    )


async def generate_title_and_story_audio(
    title: str,
    story_text_chunks: List[str],
    voice: Optional[str] = None,
    title_voice: Optional[str] = None,
    engine: Optional[str] = None,
    buffer_seconds: float = 0.0,
    **kwargs,
) -> Tuple[Path, List[AudioChunk], float, Dict[str, Any]]:
    """
    Generate separate audio for title and story, concatenate them, and return timing data.
    
    Args:
        title: Reddit post title to narrate
        story_text_chunks: List of story text chunks
        voice: Voice ID for story narration (defaults to config)
        title_voice: Voice ID for title narration (defaults to voice if not provided)
        engine: TTS engine ("edge")
        buffer_seconds: Additional buffer after title audio ends
        **kwargs: Additional arguments for TTSRouter
        
    Returns:
        Tuple of (final_audio_path, story_audio_chunks, title_duration, timing_data)
        Raises exception on error (fail-fast)
    """
    # Use same voice for title if not specified
    if title_voice is None:
        title_voice = voice
    
    async with await get_tts_client(engine=engine, voice=voice) as router:
        # Generate title audio
        logger.info(f"Generating title audio: '{title[:50]}...'")
        title_audio_path, title_duration, title_timestamps = await router.text_to_speech_with_timestamps(
            text=title,
            voice=title_voice,
            **kwargs,
        )
        
        if not title_audio_path or title_duration <= 0:
            raise RuntimeError(f"Failed to generate title audio: {title_audio_path}, duration: {title_duration}")
        
        # Calculate title word count for subtitle filtering
        title_word_count = len(title_timestamps) if title_timestamps else 0
        logger.info(f"Title audio generated: {title_audio_path} ({title_duration:.2f}s, {title_word_count} words)")
        
        # Generate story audio chunks
        logger.info(f"Generating story audio for {len(story_text_chunks)} chunks")
        story_audio_chunks = await router.generate_audio_chunks(
            text_chunks=story_text_chunks,
            voice=voice,
            with_timestamps=True,
            **kwargs,
        )
        
        if not story_audio_chunks:
            raise RuntimeError(f"Failed to generate story audio for {len(story_text_chunks)} chunks")
        
        logger.info(f"Generated {len(story_audio_chunks)} story audio chunks")
        
        # Create temporary directory for concatenation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy all audio files to temp directory to avoid path issues
            copied_audio_files = []
            
            # Copy title audio
            title_temp_path = temp_path / "title_audio.mp3"
            shutil.copy2(title_audio_path, title_temp_path)
            copied_audio_files.append(title_temp_path)
            logger.debug(f"Copied title audio to temp: {title_temp_path}")
            
            # Copy story audio chunks
            for i, chunk in enumerate(story_audio_chunks):
                if chunk.audio_path.exists() and chunk.duration_seconds > 0:
                    chunk_temp_path = temp_path / f"story_chunk_{i}.mp3"
                    shutil.copy2(chunk.audio_path, chunk_temp_path)
                    copied_audio_files.append(chunk_temp_path)
                    logger.debug(f"Copied story chunk {i} to temp: {chunk_temp_path}")
                else:
                    logger.warning(f"Skipping invalid story chunk: {chunk.chunk_id}")
            
            if len(copied_audio_files) < 2:
                raise RuntimeError(f"Not enough valid audio files to concatenate: {len(copied_audio_files)}")
            
            # Concatenate all audio files using ffmpeg filter_complex with proper re-encoding
            final_audio_path = temp_path / "final_audio.mp3"
            
            # Build filter_complex for concatenating all audio files
            filter_complex_parts = []
            input_args = []
            
            for i, audio_file in enumerate(copied_audio_files):
                input_args.extend(['-i', str(audio_file)])
                filter_complex_parts.append(f'[{i}:a]')
            
            filter_complex = ''.join(filter_complex_parts) + f'concat=n={len(copied_audio_files)}:v=0:a=1[out]'
            
            cmd = [
                'ffmpeg',
                '-y',
                *input_args,
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-c:a', 'libmp3lame',
                '-b:a', '128k',
                str(final_audio_path)
            ]
            
            logger.info(f"Concatenating {len(copied_audio_files)} audio files")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg stdout: {result.stdout}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")
            
            if not final_audio_path.exists() or final_audio_path.stat().st_size == 0:
                raise RuntimeError(f"Final audio file not created: {final_audio_path}")
            
            logger.info(f"Audio concatenated successfully: {final_audio_path} ({final_audio_path.stat().st_size} bytes)")
            
            # Calculate timing data
            from .image_generator_new import TitlePopupTimingCalculator
            timing_calc = TitlePopupTimingCalculator(
                title_audio_duration=title_duration,
                buffer_seconds=buffer_seconds
            )
            
            timing_data = timing_calc.to_dict()
            # Add title word count for subtitle filtering
            timing_data['title_word_count'] = title_word_count
            
            # Create final audio path in cache directory
            cache_dir = settings.CACHE_DIR / "final_audio"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            import hashlib
            content_hash = hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:8]
            final_cache_path = cache_dir / f"final_audio_{content_hash}.mp3"
            
            # Copy concatenated audio to cache
            shutil.copy2(final_audio_path, final_cache_path)

            # Merge title audio into first story chunk for synchronization
            if story_audio_chunks:
                first_chunk = story_audio_chunks[0]
                
                # Concatenate title audio with first chunk audio
                combined_temp_path = temp_path / "combined_first_chunk.mp3"
                
                # Use ffmpeg filter_complex to concatenate with proper re-encoding
                concat_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(title_temp_path),
                    '-i', str(first_chunk.audio_path),
                    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]',
                    '-map', '[out]',
                    '-c:a', 'libmp3lame',
                    '-b:a', '128k',
                    str(combined_temp_path)
                ]
                
                result = subprocess.run(concat_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Title+first chunk concatenation failed: {result.stderr}")
                    raise RuntimeError(f"Failed to concatenate title with first chunk: {result.stderr}")
                
                if not combined_temp_path.exists() or combined_temp_path.stat().st_size == 0:
                    raise RuntimeError(f"Combined audio file not created: {combined_temp_path}")
                
                # Cache the combined audio
                combined_cache_path = cache_dir / f"combined_first_chunk_{content_hash}.mp3"
                shutil.copy2(combined_temp_path, combined_cache_path)
                
                # Get file size of combined audio
                combined_file_size = combined_cache_path.stat().st_size
                
                # Adjust timestamps
                combined_timestamps = []
                
                # Add title timestamps (if available)
                if title_timestamps:
                    combined_timestamps.extend(title_timestamps)
                
                # Add first chunk timestamps shifted by title duration
                if first_chunk.word_timestamps:
                    for ts in first_chunk.word_timestamps:
                        shifted_ts = WordTimestamp(
                            word=ts.word,
                            start=ts.start + title_duration,
                            end=ts.end + title_duration,
                            confidence=ts.confidence
                        )
                        combined_timestamps.append(shifted_ts)
                
                # Update first chunk with combined audio and timestamps
                first_chunk.audio_path = combined_cache_path
                first_chunk.duration_seconds += title_duration
                first_chunk.text = f"{title} {first_chunk.text}"
                first_chunk.word_timestamps = combined_timestamps
                first_chunk.file_size_bytes = combined_file_size
                
                logger.info(f"Merged title into first story chunk: {combined_cache_path} ({combined_file_size} bytes)")

            logger.info(f"Final audio cached: {final_cache_path}")
            logger.info(f"Title duration: {title_duration:.2f}s ({title_word_count} words), Story chunks: {len(story_audio_chunks)}")

            return final_cache_path, story_audio_chunks, title_duration, timing_data


# Test function
async def test_tts_router():
    """Test the TTS router with Edge TTS engine."""
    import asyncio
    
    test_chunks = [
        "Hello, this is a test of the TTS router system.",
        "This should work with Edge TTS.",
    ]
    
    # Test with Edge TTS
    print("Testing with Edge TTS engine...")
    async with await get_tts_client(engine="edge") as router:
        print(f"Using engine: {router.config.engine}")
        
        voices = await router.get_available_voices()
        print(f"Available voices: {len(voices)}")
        
        audio_chunks = await router.generate_audio_chunks(
            test_chunks,
            with_timestamps=True
        )
        
        print(f"Generated {len(audio_chunks)} audio chunks")
        for i, chunk in enumerate(audio_chunks, 1):
            print(f"Chunk {i}: {chunk.duration_seconds:.1f}s, {len(chunk.word_timestamps or [])} word timestamps")
    
    print("\nTesting factory function...")
    chunks = await generate_story_audio(
        test_chunks[:1],
        engine="edge",
        with_timestamps=True
    )
    print(f"Generated {len(chunks)} chunk(s) via factory")


if __name__ == "__main__":
    asyncio.run(test_tts_router())