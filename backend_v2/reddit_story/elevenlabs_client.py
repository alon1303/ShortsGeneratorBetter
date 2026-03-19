import os
import hashlib
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import uuid

from elevenlabs.client import ElevenLabs
from config.settings import settings
from .models import WordTimestamp, AudioChunk

logger = logging.getLogger(__name__)

class ElevenLabsClient:
    """Async client for ElevenLabs Text-to-Speech with modern SDK support."""
    
    def __init__(
        self,
        voice: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        model: str = "eleven_multilingual_v2"
    ):
        self.api_key = settings.ELEVENLABS_API_KEY
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is not set in settings/env")
            
        self.client = ElevenLabs(api_key=self.api_key)
        self.voice = voice or settings.get_voice_id("adam")
        self.model = model
        self.cache_dir = cache_dir or settings.CACHE_DIR / "elevenlabs"
        self.voices_dir = self.cache_dir / "voices"
        
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ElevenLabs client initialized: voice={self.voice}, model={self.model}")

    def _generate_cache_key(self, text: str, voice: str) -> str:
        params_str = f"{text}_{voice}_{self.model}"
        return hashlib.md5(params_str.encode('utf-8')).hexdigest()

    async def _estimate_duration(self, audio_path: Path) -> float:
        """Get accurate duration using ffprobe."""
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'json', str(audio_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return float(json.loads(result.stdout)['format']['duration'])
        except Exception:
            pass
        return 0.0

    async def text_to_speech_with_timestamps(
        self,
        text: str,
        voice: Optional[str] = None,
        use_cache: bool = True,
    ) -> Tuple[Optional[Path], float, Optional[List[WordTimestamp]]]:
        """
        Convert text to speech. 
        Note: Free ElevenLabs API doesn't easily provide word-level timestamps in a single call 
        like Edge-TTS. This version focuses on fixing the 'generate' error first.
        """
        voice_id = voice or self.voice
        cache_key = self._generate_cache_key(text, voice_id)
        
        if use_cache:
            pattern = f"{cache_key}_*.mp3"
            cached_files = list(self.voices_dir.glob(pattern))
            if cached_files:
                cached_path = sorted(cached_files)[-1]
                duration = await self._estimate_duration(cached_path)
                return cached_path, duration, None

        try:
            logger.info(f"Generating ElevenLabs TTS for {len(text)} chars")
            
            # THE FIX: Use text_to_speech.convert instead of generate
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=self.model,
                output_format="mp3_44100_128"
            )
            
            # Collect all bytes from the generator
            audio_data = b"".join(list(audio_generator))
            
            timestamp = int(time.time())
            file_path = self.voices_dir / f"{cache_key}_{timestamp}.mp3"
            
            with open(file_path, "wb") as f:
                f.write(audio_data)
                
            duration = await self._estimate_duration(file_path)
            return file_path, duration, None # Timestamps require a more complex streaming setup
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {str(e)}")
            raise

    async def generate_audio_chunks(
        self,
        text_chunks: List[str],
        voice: Optional[str] = None,
        **kwargs
    ) -> List[AudioChunk]:
        chunks = []
        for text in text_chunks:
            path, duration, _ = await self.text_to_speech_with_timestamps(text, voice)
            chunks.append(AudioChunk(
                chunk_id=str(uuid.uuid4())[:8],
                text=text,
                audio_path=path,
                duration_seconds=duration,
                voice_id=voice or self.voice,
                file_size_bytes=path.stat().st_size if path else 0
            ))
        return chunks

    async def get_available_voices(self) -> List[Dict[str, Any]]:
        response = self.client.voices.get_all()
        return [{"voice_id": v.voice_id, "name": v.name} for v in response.voices]
    
    async def close(self):
        pass