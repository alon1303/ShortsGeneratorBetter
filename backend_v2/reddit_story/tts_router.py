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
        
        if self.config.engine == "edge":
            return await client.text_to_speech_with_timestamps(
                text=text,
                voice=voice,
                use_cache=self.config.use_cache,
                **kwargs,
            )
        elif self.config.engine == "elevenlabs":
            return await client.text_to_speech_with_timestamps(
                text=text,
                voice_id=voice,
                use_cache=self.config.use_cache,
                **kwargs,
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