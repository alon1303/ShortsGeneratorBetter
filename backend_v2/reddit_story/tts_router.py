"""
TTS Router/Factory for selecting between Edge TTS and ElevenLabs TTS engines.
Routes requests to the appropriate TTS client based on configuration.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from config.settings import settings
from .elevenlabs_client import ElevenLabsClient, WordTimestamp, AudioChunk
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
    engine: str  # "edge" or "elevenlabs"
    voice_id: Optional[str] = None
    cache_dir: Optional[Path] = None
    use_cache: bool = True
    
    @classmethod
    def from_settings(cls, voice_id: Optional[str] = None, cache_dir: Optional[Path] = None):
        """Create TTSConfig from application settings."""
        return cls(
            engine=settings.TTS_ENGINE.lower(),
            voice_id=voice_id,
            cache_dir=cache_dir,
            use_cache=settings.ENABLE_CACHE
        )


class TTSRouter:
    """
    Router that selects the appropriate TTS client based on configuration.
    Provides a unified interface for both Edge TTS and ElevenLabs TTS.
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
            elif self.config.engine == "elevenlabs":
                self._client = ElevenLabsClient(
                    voice_id=self.config.voice_id,
                    cache_dir=self.config.cache_dir
                )
            else:
                raise ValueError(f"Unknown TTS engine: {self.config.engine}. Use 'edge' or 'elevenlabs'")
        
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
        elif self.config.engine == "elevenlabs":
            return await client.text_to_speech_with_timestamps(
                text=text,
                voice_id=voice,
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
        elif self.config.engine == "elevenlabs":
            return await client.text_to_speech(
                text=text,
                voice_id=voice,
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
        elif self.config.engine == "elevenlabs":
            return await client.generate_audio_chunks(
                text_chunks=text_chunks,
                voice_id=voice,
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
            if self.config.engine == "elevenlabs":
                await self._client.close()
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
        engine: TTS engine ("edge" or "elevenlabs"), defaults to settings.TTS_ENGINE
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
        engine: Override TTS engine ("edge" or "elevenlabs")
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
    Uses "voice_id" parameter name for ElevenLabs compatibility.
    
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
    buffer_seconds: float = 0.2,
    **kwargs,
) -> Tuple[Path, List[AudioChunk], float, Dict[str, Any]]:
    """
    Generate separate audio for title and story, concatenate them, and return timing data.
    
    Args:
        title: Reddit post title to narrate
        story_text_chunks: List of story text chunks
        voice: Voice ID for story narration (defaults to config)
        title_voice: Voice ID for title narration (defaults to voice if not provided)
        engine: TTS engine ("edge" or "elevenlabs")
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
            
            # Create file list for ffmpeg using forward slashes for Windows compatibility
            filelist_path = temp_path / "concat_list.txt"
            with open(filelist_path, 'w', encoding='utf-8') as f:
                for audio_file in copied_audio_files:
                    # Use forward slashes for Windows compatibility with ffmpeg
                    # Convert Path to string and replace backslashes with forward slashes
                    path_str = str(audio_file).replace('\\', '/')
                    # Escape single quotes for ffmpeg concat format
                    path_str = path_str.replace("'", "'\\''")
                    f.write(f"file '{path_str}'\n")
            
            logger.debug(f"Created concat list at: {filelist_path}")
            with open(filelist_path, 'r') as f:
                logger.debug(f"Concat list contents:\n{f.read()}")
            
            # Concatenate audio files using ffmpeg
            final_audio_path = temp_path / "final_audio.mp3"
            
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(filelist_path),
                '-c', 'copy',  # Copy codec (no re-encoding)
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
            from .image_generator import TitlePopupTimingCalculator
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
            
            logger.info(f"Final audio cached: {final_cache_path}")
            logger.info(f"Title duration: {title_duration:.2f}s ({title_word_count} words), Story chunks: {len(story_audio_chunks)}")
            
            return final_cache_path, story_audio_chunks, title_duration, timing_data


# Test function
async def test_tts_router():
    """Test the TTS router with different engines."""
    import asyncio
    
    test_chunks = [
        "Hello, this is a test of the TTS router system.",
        "This should work with either Edge TTS or ElevenLabs.",
    ]
    
    # Test with Edge TTS (free)
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
    
    # Test with ElevenLabs (if configured)
    if settings.is_elevenlabs_configured():
        print("\nTesting with ElevenLabs engine...")
        async with await get_tts_client(engine="elevenlabs") as router:
            print(f"Using engine: {router.config.engine}")
            
            voices = await router.get_available_voices()
            print(f"Available voices: {len(voices)}")
    else:
        print("\nSkipping ElevenLabs test (not configured)")
    
    print("\nTesting factory function...")
    chunks = await generate_story_audio(
        test_chunks[:1],
        engine="edge",
        with_timestamps=True
    )
    print(f"Generated {len(chunks)} chunk(s) via factory")


if __name__ == "__main__":
    asyncio.run(test_tts_router())