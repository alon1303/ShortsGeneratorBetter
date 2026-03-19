"""
TTS Router/Factory for Edge TTS and ElevenLabs engines.
Routes requests to the appropriate TTS client.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from config.settings import settings
from .models import WordTimestamp, AudioChunk
from .edgetts_client import EdgeTTSClient
from .elevenlabs_client import ElevenLabsClient
import subprocess
import tempfile
import shutil
import asyncio
import uuid

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
    def from_settings(cls, engine: Optional[str] = None, voice_id: Optional[str] = None, cache_dir: Optional[Path] = None):
        """Create TTSConfig from application settings."""
        return cls(
            engine=engine or settings.TTS_ENGINE.lower(),
            voice_id=voice_id or settings.get_voice_id(),
            cache_dir=cache_dir,
            use_cache=settings.ENABLE_CACHE
        )


class TTSRouter:
    """
    Router that selects the appropriate TTS client based on configuration.
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
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
                # Ensure the voice ID is valid for ElevenLabs (not an Edge TTS ID)
                voice_id = self.config.voice_id
                if voice_id and ("neural" in voice_id.lower() or "en-" in voice_id.lower()):
                    logger.warning(f"Overriding Edge TTS voice '{voice_id}' with ElevenLabs default for ElevenLabs engine")
                    voice_id = settings.get_voice_id("adam", engine="elevenlabs")
                
                # Fixed: Use 'voice' instead of 'voice_id' to match ElevenLabsClient.__init__
                self._client = ElevenLabsClient(
                    voice=voice_id,
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
        client = await self._get_client()
        voice = voice or self.config.voice_id
        
        logger.info(f"TTSRouter: engine={self.config.engine}, requested_voice={voice}")
        
        # Sanitize voice for ElevenLabs engine to prevent 400 errors
        if self.config.engine == "elevenlabs" and voice:
            if "neural" in voice.lower() or "en-" in voice.lower():
                logger.warning(f"TTSRouter: Sanitizing Edge voice '{voice}' for ElevenLabs engine")
                voice = None # Force client to use its own sanitized default
        
        logger.debug(f"Routing TTS request to {self.config.engine} engine")
        
        # Remove 'use_cache' from kwargs if present
        kwargs_without_use_cache = {k: v for k, v in kwargs.items() if k != 'use_cache'}
        
        return await client.text_to_speech_with_timestamps(
            text=text,
            voice=voice,
            use_cache=self.config.use_cache,
            **kwargs_without_use_cache,
        )
    
    async def text_to_speech(self, text: str, voice: Optional[str] = None, **kwargs) -> Tuple[Optional[Path], float]:
        client = await self._get_client()
        voice = voice or self.config.voice_id
        return await client.text_to_speech(text=text, voice=voice, use_cache=self.config.use_cache, **kwargs)
    
    async def generate_audio_chunks(
        self,
        text_chunks: List[str],
        voice: Optional[str] = None,
        with_timestamps: bool = True,
        **kwargs,
    ) -> List[AudioChunk]:
        client = await self._get_client()
        voice = voice or self.config.voice_id
        return await client.generate_audio_chunks(text_chunks=text_chunks, voice=voice, with_timestamps=with_timestamps, **kwargs)
    
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        client = await self._get_client()
        return await client.get_available_voices()
    
    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def get_tts_client(engine: Optional[str] = None, voice: Optional[str] = None, **kwargs) -> TTSRouter:
    config = TTSConfig.from_settings(engine=engine, voice_id=voice)
    return TTSRouter(config)

async def generate_title_and_story_audio(
    title: str,
    story_text_chunks: List[str],
    voice: Optional[str] = None,
    engine: Optional[str] = None,
    buffer_seconds: float = 0.0,
    **kwargs,
) -> Tuple[Path, List[AudioChunk], float, Dict[str, Any]]:
    
    async with await get_tts_client(engine=engine, voice=voice) as router:
        # Generate title audio
        title_audio_path, title_duration, title_timestamps = await router.text_to_speech_with_timestamps(
            text=title, voice=voice, **kwargs
        )
        
        # Generate story audio chunks
        story_audio_chunks = await router.generate_audio_chunks(
            text_chunks=story_text_chunks, voice=voice, with_timestamps=True, **kwargs
        )
        
        # Concatenation and Timing Logic
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            final_audio_path = temp_path / "final_audio.mp3"
            
            # Simple FFmpeg concat (simplified for briefness, keeping your existing logic structure)
            input_args = ['-i', str(title_audio_path)]
            for chunk in story_audio_chunks:
                input_args.extend(['-i', str(chunk.audio_path)])
                
            filter_complex = "".join([f"[{i}:a]" for i in range(len(story_audio_chunks) + 1)]) + f"concat=n={len(story_audio_chunks)+1}:v=0:a=1[out]"
            cmd = ['ffmpeg', '-y'] + input_args + ['-filter_complex', filter_complex, '-map', '[out]', '-c:a', 'libmp3lame', str(final_audio_path)]
            subprocess.run(cmd, capture_output=True)
            
            # Cache the result
            cache_dir = settings.CACHE_DIR / "final_audio"
            cache_dir.mkdir(parents=True, exist_ok=True)
            final_cache_path = cache_dir / f"preview_{uuid.uuid4().hex[:8]}.mp3"
            shutil.copy2(final_audio_path, final_cache_path)

            # Mock timing data for preview
            timing_data = {
                "title_duration": title_duration, 
                "buffer": buffer_seconds, 
                "title_word_count": len(title_timestamps) if title_timestamps is not None else 0
            }
            
            return final_cache_path, story_audio_chunks, title_duration, timing_data