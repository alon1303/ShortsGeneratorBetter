"""
ElevenLabs Text-to-Speech client for generating voiceovers for Reddit stories.
Provides async API integration with caching and error handling.
"""

import asyncio
import aiohttp
import aiofiles
import json
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import uuid

from config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class WordTimestamp:
    """Represents a word with its timing information."""
    word: str
    start: float  # Start time in seconds
    end: float    # End time in seconds
    confidence: float  # Confidence score (0.0-1.0)

@dataclass
class AudioChunk:
    """Represents a generated audio chunk with metadata."""
    chunk_id: str
    text: str
    audio_path: Path
    duration_seconds: float
    voice_id: str
    file_size_bytes: int
    word_timestamps: Optional[List[WordTimestamp]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "audio_path": str(self.audio_path),
            "duration_seconds": self.duration_seconds,
            "voice_id": self.voice_id,
            "file_size_bytes": self.file_size_bytes,
            "has_word_timestamps": self.word_timestamps is not None and len(self.word_timestamps) > 0,
            "word_count": len(self.word_timestamps) if self.word_timestamps else 0,
        }

class ElevenLabsClient:
    """Async client for ElevenLabs Text-to-Speech API."""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ):
        """
        Initialize ElevenLabs client.
        
        Args:
            api_key: ElevenLabs API key (defaults to settings.ELEVENLABS_API_KEY)
            voice_id: Default voice ID (defaults to settings.DEFAULT_VOICE_ID)
            cache_dir: Directory to cache generated audio files
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        self.default_voice_id = voice_id or settings.DEFAULT_VOICE_ID
        self.timeout = timeout
        
        # Set up cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = settings.CACHE_DIR / "elevenlabs"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create voices subdirectory
        self.voices_dir = self.cache_dir / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        # Session will be created on first use
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            f"ElevenLabs client initialized: "
            f"voice={self.default_voice_id}, cache={self.cache_dir}"
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("ElevenLabs client session closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _generate_cache_key(self, text: str, voice_id: str, **kwargs) -> str:
        """
        Generate a cache key for text and voice combination.
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use
            **kwargs: Additional parameters that affect output
            
        Returns:
            MD5 hash string for caching
        """
        # Create a string representation of all parameters
        params_str = f"{text}_{voice_id}_{json.dumps(kwargs, sort_keys=True)}"
        
        # Generate MD5 hash
        return hashlib.md5(params_str.encode('utf-8')).hexdigest()
    
    def _get_cached_audio_path(self, cache_key: str) -> Optional[Path]:
        """
        Check if audio is already cached.
        
        Args:
            cache_key: Cache key for the audio
            
        Returns:
            Path to cached audio file if exists, None otherwise
        """
        # Look for files with this cache key
        pattern = f"{cache_key}_*.mp3"
        cached_files = list(self.voices_dir.glob(pattern))
        
        if cached_files:
            # Return the most recent file
            return sorted(cached_files, key=lambda p: p.stat().st_mtime)[-1]
        
        return None
    
    async def _save_audio_to_cache(
        self, 
        cache_key: str, 
        audio_data: bytes,
        text: str,
        voice_id: str
    ) -> Path:
        """
        Save audio data to cache.
        
        Args:
            cache_key: Cache key for the audio
            audio_data: Raw audio bytes
            text: Original text (for metadata)
            voice_id: Voice ID used
            
        Returns:
            Path to saved audio file
        """
        # Generate filename with timestamp
        timestamp = int(time.time())
        filename = f"{cache_key}_{timestamp}.mp3"
        filepath = self.voices_dir / filename
        
        # Save audio file
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(audio_data)
        
        # Save metadata
        metadata = {
            "cache_key": cache_key,
            "text": text,
            "voice_id": voice_id,
            "timestamp": timestamp,
            "file_size": len(audio_data),
        }
        
        metadata_path = filepath.with_suffix('.json')
        async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        logger.debug(f"Audio cached: {filepath} ({len(audio_data)} bytes)")
        
        return filepath
    
    async def _estimate_audio_duration(self, audio_path: Path) -> float:
        """
        Get accurate audio duration using ffprobe.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Accurate duration in seconds
        """
        try:
            import subprocess
            import json
            
            # Use ffprobe to get accurate duration
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'json',
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                logger.debug(f"Accurate audio duration from ffprobe: {duration:.3f}s")
                return duration
            else:
                logger.warning(f"ffprobe failed for {audio_path}: {result.stderr}")
                # Fallback to file size estimation
                file_size = audio_path.stat().st_size
                estimated_duration = file_size / 16000
                logger.warning(f"Using estimated duration: {estimated_duration:.3f}s (file size: {file_size} bytes)")
                return estimated_duration
                
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
            # Fallback: estimate based on text length (150 words/minute)
            return 0.0
    
    async def text_to_speech_with_timestamps(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
        optimize_streaming_latency: int = 0,
        use_cache: bool = True,
    ) -> Tuple[Optional[Path], float, Optional[List[WordTimestamp]]]:
        """
        Convert text to speech using ElevenLabs API with word-level timestamps.
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use (defaults to self.default_voice_id)
            model_id: TTS model to use
            stability: Voice stability (0.0-1.0)
            similarity_boost: Voice similarity boost (0.0-1.0)
            style: Speaking style (0.0-1.0)
            use_speaker_boost: Whether to use speaker boost
            optimize_streaming_latency: Latency optimization (0-4)
            use_cache: Whether to use cached audio if available
            
        Returns:
            Tuple of (audio_file_path, duration_seconds, word_timestamps) or (None, 0.0, None) on error
        """
        if not self.api_key:
            logger.error("ElevenLabs API key not configured")
            return None, 0.0, None
        
        voice_id = voice_id or self.default_voice_id
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            text, 
            voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost,
        )
        
        # Check cache first - for timestamps we need to check both audio and timestamp cache
        if use_cache:
            cached_path = self._get_cached_audio_path(cache_key)
            if cached_path:
                # Check if we have timestamp metadata
                timestamp_path = cached_path.with_suffix('.timestamps.json')
                if timestamp_path.exists():
                    try:
                        async with aiofiles.open(timestamp_path, 'r', encoding='utf-8') as f:
                            timestamp_data = json.loads(await f.read())
                        
                        # Parse word timestamps
                        word_timestamps = []
                        for ts in timestamp_data.get('word_timestamps', []):
                            word_timestamps.append(WordTimestamp(
                                word=ts['word'],
                                start=ts['start'],
                                end=ts['end'],
                                confidence=ts.get('confidence', 1.0)
                            ))
                        
                        duration = await self._estimate_audio_duration(cached_path)
                        logger.debug(f"Using cached audio with timestamps: {cached_path} ({duration:.1f}s, {len(word_timestamps)} words)")
                        return cached_path, duration, word_timestamps
                    except Exception as e:
                        logger.warning(f"Failed to load cached timestamps: {e}")
                
                # If we have audio but no timestamps, we still return the audio
                duration = await self._estimate_audio_duration(cached_path)
                logger.debug(f"Using cached audio (no timestamps): {cached_path} ({duration:.1f}s)")
                return cached_path, duration, None
        
        # Prepare request payload
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }
        
        # Make API request to endpoint with timestamps
        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/with-timestamps"
        
        # Add query parameters for optimization
        params = {}
        if optimize_streaming_latency > 0:
            params["optimize_streaming_latency"] = optimize_streaming_latency
        
        try:
            session = await self._get_session()
            
            logger.info(f"Generating TTS with timestamps for {len(text)} characters with voice {voice_id}")
            
            async with session.post(
                url, 
                json=payload, 
                params=params,
                headers={"xi-api-key": self.api_key}
            ) as response:
                # DEBUG: Print raw response info as requested
                print(f"DEBUG: ElevenLabs API Response Status: {response.status}")
                response_text_raw = await response.text()
                print(f"DEBUG: ElevenLabs API Response Text (first 200 chars): {response_text_raw[:200]}")
                
                if response.status == 200:
                    # Check content type
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        # Parse the response which contains both audio and timestamps
                        response_data = await response.json()
                        
                        # Extract audio data (base64 encoded)
                        audio_base64 = response_data.get('audio_base64')
                        if not audio_base64:
                            logger.error("No audio data in response")
                            return None, 0.0, None
                        
                        # Decode base64 audio
                        import base64
                        audio_data = base64.b64decode(audio_base64)
                        
                        # Save to cache
                        audio_path = await self._save_audio_to_cache(
                            cache_key, audio_data, text, voice_id
                        )
                        
                        # Extract word timestamps from character-level alignment data
                        word_timestamps = []
                        alignment_data = response_data.get('alignment')
                        if alignment_data and isinstance(alignment_data, dict):
                            # Get character arrays from the alignment dictionary
                            characters = alignment_data.get('characters', [])
                            # Try different key names for start/end times
                            start_times = alignment_data.get('character_start_times_seconds', [])
                            end_times = alignment_data.get('character_end_times_seconds', [])
                            
                            # Fallback to millisecond keys if second keys not found
                            if not start_times:
                                start_times_ms = alignment_data.get('char_start_times_ms', [])
                                start_times = [ms / 1000.0 for ms in start_times_ms]
                            if not end_times:
                                end_times_ms = alignment_data.get('char_end_times_ms', [])
                                end_times = [ms / 1000.0 for ms in end_times_ms]
                            
                            # Ensure all arrays have the same length
                            if characters and start_times and end_times:
                                min_len = min(len(characters), len(start_times), len(end_times))
                                if min_len > 0:
                                    # Group characters into words based on spaces
                                    current_word = []
                                    word_start_time = 0.0
                                    
                                    for i in range(min_len):
                                        char = characters[i]
                                        char_start = start_times[i]
                                        char_end = end_times[i]
                                        
                                        # If this is the first character of a word, record start time
                                        if not current_word:
                                            word_start_time = char_start
                                        
                                        # Add character to current word
                                        current_word.append(char)
                                        
                                        # Check if this character ends a word (space or last character)
                                        is_space = char == ' '
                                        is_last_char = i == min_len - 1
                                        
                                        if is_space or is_last_char:
                                            # Remove trailing space if present
                                            if is_space and current_word:
                                                current_word.pop()  # Remove the space
                                            
                                            if current_word:  # Only create word if we have characters
                                                word_text = ''.join(current_word).strip()
                                                if word_text:  # Skip empty words
                                                    # Word end time is the end time of the last character
                                                    word_end_time = char_end
                                                    
                                                    word_timestamps.append(WordTimestamp(
                                                        word=word_text,
                                                        start=word_start_time,
                                                        end=word_end_time,
                                                        confidence=1.0  # Default confidence
                                                    ))
                                                
                                                # Reset for next word
                                                current_word = []
                                    
                                    logger.debug(f"Extracted {len(word_timestamps)} words from {min_len} characters")
                                else:
                                    logger.warning("Alignment data has zero-length arrays")
                            else:
                                logger.warning("Missing character or timing data in alignment")
                        elif alignment_data:
                            logger.warning(f"Unexpected alignment data type: {type(alignment_data)}")
                        
                        # Save timestamps to cache
                        if word_timestamps:
                            timestamp_path = audio_path.with_suffix('.timestamps.json')
                            timestamp_data = {
                                'word_timestamps': [
                                    {
                                        'word': ts.word,
                                        'start': ts.start,
                                        'end': ts.end,
                                        'confidence': ts.confidence
                                    }
                                    for ts in word_timestamps
                                ]
                            }
                            
                            async with aiofiles.open(timestamp_path, 'w', encoding='utf-8') as f:
                                await f.write(json.dumps(timestamp_data, indent=2))
                        
                        # Estimate duration
                        duration = await self._estimate_audio_duration(audio_path)
                        
                        logger.info(f"TTS with timestamps generated: {audio_path} ({duration:.1f}s, {len(word_timestamps)} words)")
                        return audio_path, duration, word_timestamps
                    else:
                        # The endpoint might not support timestamps and returns regular audio
                        logger.warning(f"Timestamps endpoint returned non-JSON response (Content-Type: {content_type}), falling back to regular TTS")
                        audio_data = await response.read()
                        
                        # Save to cache
                        audio_path = await self._save_audio_to_cache(
                            cache_key, audio_data, text, voice_id
                        )
                        
                        # Estimate duration
                        duration = await self._estimate_audio_duration(audio_path)
                        
                        logger.info(f"TTS generated (no timestamps): {audio_path} ({duration:.1f}s)")
                        return audio_path, duration, None
                else:
                    error_text = await response.text()
                    error_msg = f"ElevenLabs API error (with timestamps): {response.status} - {error_text}"
                    
                    # Handle specific error cases
                    if response.status == 401:
                        logger.error(f"{error_msg} - Check API key and permissions")
                    elif response.status == 402:
                        logger.error(f"{error_msg} - Payment required or quota exceeded")
                    elif response.status == 429:
                        logger.error(f"{error_msg} - Rate limited, try again later")
                    elif "Model is not available on the free tier" in error_text:
                        logger.error(f"{error_msg} - Using free-tier incompatible model")
                        # Try with a different free-tier model
                        if model_id != "eleven_turbo_v2_5":
                            logger.info(f"Retrying with free-tier model: eleven_turbo_v2_5")
                            return await self.text_to_speech_with_timestamps(
                                text=text,
                                voice_id=voice_id,
                                model_id="eleven_turbo_v2_5",  # Alternative free-tier model
                                stability=stability,
                                similarity_boost=similarity_boost,
                                style=style,
                                use_speaker_boost=use_speaker_boost,
                                optimize_streaming_latency=optimize_streaming_latency,
                                use_cache=use_cache,
                            )
                    elif "Endpoint not found" in error_text or "with-timestamps" in error_text:
                        logger.warning(f"Timestamps endpoint not available, falling back to regular TTS")
                        # Fall back to regular TTS
                        audio_path, duration = await self.text_to_speech(
                            text=text,
                            voice_id=voice_id,
                            model_id=model_id,
                            stability=stability,
                            similarity_boost=similarity_boost,
                            style=style,
                            use_speaker_boost=use_speaker_boost,
                            optimize_streaming_latency=optimize_streaming_latency,
                            use_cache=use_cache,
                        )
                        return audio_path, duration, None
                    else:
                        logger.error(error_msg)
                    
                    return None, 0.0, None
                    
        except asyncio.TimeoutError:
            logger.error(f"ElevenLabs API timeout after {self.timeout}s")
            raise  # Re-raise to crash loudly
        except aiohttp.ClientError as e:
            logger.error(f"ElevenLabs API client error: {e}")
            raise  # Re-raise to crash loudly
        # REMOVED generic Exception handler - let it crash
    
    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_multilingual_v2",  # Free-tier compatible model
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
        optimize_streaming_latency: int = 0,
        use_cache: bool = True,
    ) -> Tuple[Optional[Path], float]:
        """
        Convert text to speech using ElevenLabs API.
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use (defaults to self.default_voice_id)
            model_id: TTS model to use
            stability: Voice stability (0.0-1.0)
            similarity_boost: Voice similarity boost (0.0-1.0)
            style: Speaking style (0.0-1.0)
            use_speaker_boost: Whether to use speaker boost
            optimize_streaming_latency: Latency optimization (0-4)
            use_cache: Whether to use cached audio if available
            
        Returns:
            Tuple of (audio_file_path, duration_seconds) or (None, 0.0) on error
        """
        # Use the with-timestamps endpoint but ignore timestamps for backward compatibility
        audio_path, duration, _ = await self.text_to_speech_with_timestamps(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost,
            optimize_streaming_latency=optimize_streaming_latency,
            use_cache=use_cache,
        )
        return audio_path, duration
    
    async def generate_audio_chunks(
        self,
        text_chunks: List[str],
        voice_id: Optional[str] = None,
        with_timestamps: bool = True,
        **tts_kwargs,
    ) -> List[AudioChunk]:
        """
        Generate audio for multiple text chunks.
        
        Args:
            text_chunks: List of text chunks to convert
            voice_id: Voice ID to use
            with_timestamps: Whether to request word-level timestamps
            **tts_kwargs: Additional arguments for text_to_speech
            
        Returns:
            List of AudioChunk objects
        """
        voice_id = voice_id or self.default_voice_id
        
        logger.info(f"Generating audio for {len(text_chunks)} chunks with voice {voice_id} (timestamps: {with_timestamps})")
        
        audio_chunks = []
        
        for i, text in enumerate(text_chunks, 1):
            chunk_id = str(uuid.uuid4())[:8]
            
            logger.debug(f"Processing chunk {i}/{len(text_chunks)}: {len(text)} chars")
            
            # Generate audio with or without timestamps
            if with_timestamps:
                audio_path, duration, word_timestamps = await self.text_to_speech_with_timestamps(
                    text, 
                    voice_id=voice_id,
                    **tts_kwargs,
                )
            else:
                audio_path, duration = await self.text_to_speech(
                    text, 
                    voice_id=voice_id,
                    **tts_kwargs,
                )
                word_timestamps = None
            
            if audio_path:
                # Get file size
                file_size = audio_path.stat().st_size
                
                # Create AudioChunk object
                chunk = AudioChunk(
                    chunk_id=chunk_id,
                    text=text,
                    audio_path=audio_path,
                    duration_seconds=duration,
                    voice_id=voice_id,
                    file_size_bytes=file_size,
                    word_timestamps=word_timestamps,
                )
                
                audio_chunks.append(chunk)
                if word_timestamps:
                    logger.info(f"Chunk {i} generated: {duration:.1f}s, {file_size} bytes, {len(word_timestamps)} word timestamps")
                else:
                    logger.info(f"Chunk {i} generated: {duration:.1f}s, {file_size} bytes")
            else:
                logger.error(f"Failed to generate audio for chunk {i}")
                # Create a placeholder chunk to maintain order
                chunk = AudioChunk(
                    chunk_id=chunk_id,
                    text=text,
                    audio_path=Path(""),
                    duration_seconds=0.0,
                    voice_id=voice_id,
                    file_size_bytes=0,
                    word_timestamps=None,
                )
                audio_chunks.append(chunk)
        
        # Log summary
        successful = sum(1 for c in audio_chunks if c.duration_seconds > 0)
        total_duration = sum(c.duration_seconds for c in audio_chunks)
        chunks_with_timestamps = sum(1 for c in audio_chunks if c.word_timestamps)
        
        logger.info(
            f"Audio generation complete: {successful}/{len(text_chunks)} successful, "
            f"total duration: {total_duration:.1f}s, "
            f"{chunks_with_timestamps} chunks with word timestamps"
        )
        
        return audio_chunks
    
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Get list of available voices from ElevenLabs API.
        
        Returns:
            List of voice information dictionaries
        """
        if not self.api_key:
            logger.error("ElevenLabs API key not configured")
            return []
        
        url = f"{self.BASE_URL}/voices"
        
        try:
            session = await self._get_session()
            
            async with session.get(url, headers={"xi-api-key": self.api_key}) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("voices", [])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get voices: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return []
    
    async def get_voice_details(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific voice.
        
        Args:
            voice_id: Voice ID to get details for
            
        Returns:
            Voice details dictionary or None if not found
        """
        if not self.api_key:
            logger.error("ElevenLabs API key not configured")
            return None
        
        url = f"{self.BASE_URL}/voices/{voice_id}"
        
        try:
            session = await self._get_session()
            
            async with session.get(url, headers={"xi-api-key": self.api_key}) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get voice details: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting voice details: {e}")
            return None
    
    def cleanup_old_cache(self, max_age_hours: int = 24) -> int:
        """
        Clean up old cache files.
        
        Args:
            max_age_hours: Maximum age of cache files in hours
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filepath in self.voices_dir.glob("*.mp3"):
            try:
                file_age = current_time - filepath.stat().st_mtime
                
                if file_age > max_age_seconds:
                    # Delete audio file
                    filepath.unlink()
                    
                    # Delete metadata file if exists
                    metadata_path = filepath.with_suffix('.json')
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    deleted_count += 1
                    logger.debug(f"Deleted old cache file: {filepath}")
                    
            except Exception as e:
                logger.warning(f"Failed to delete cache file {filepath}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old cache files")
        
        return deleted_count


# Utility functions for direct use
async def generate_story_audio(
    text_chunks: List[str],
    voice_id: Optional[str] = None,
    with_timestamps: bool = True,
    **kwargs,
) -> List[AudioChunk]:
    """
    Convenience function to generate audio for story chunks.
    
    Args:
        text_chunks: List of text chunks to convert
        voice_id: Voice ID to use
        with_timestamps: Whether to request word-level timestamps
        **kwargs: Additional arguments for ElevenLabsClient
        
    Returns:
        List of AudioChunk objects
    """
    async with ElevenLabsClient(**kwargs) as client:
        return await client.generate_audio_chunks(text_chunks, voice_id, with_timestamps=with_timestamps)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def example():
        # Check if API key is configured
        if not settings.ELEVENLABS_API_KEY:
            print("⚠️  ElevenLabs API key not configured.")
            print("   Set ELEVENLABS_API_KEY in your .env file")
            print("   Get API key from: https://elevenlabs.io/app")
            return
        
        # Create client
        async with ElevenLabsClient() as client:
            # Test text chunks
            test_chunks = [
                "Hello, this is a test of the ElevenLabs text-to-speech system.",
                "This is the second chunk of text for testing purposes.",
                "And this is the third and final test chunk."
            ]
            
            print(f"Generating audio for {len(test_chunks)} test chunks...")
            
            # Generate audio
            audio_chunks = await client.generate_audio_chunks(test_chunks)
            
            print(f"\nGenerated {len(audio_chunks)} audio chunks:")
            for i, chunk in enumerate(audio_chunks, 1):
                print(f"\nChunk {i}:")
                print(f"  Duration: {chunk.duration_seconds:.1f}s")
                print(f"  File size: {chunk.file_size_bytes} bytes")
                print(f"  Voice: {chunk.voice_id}")
                print(f"  Path: {chunk.audio_path}")
            
            # Test cache functionality
            print(f"\nTesting cache...")
            cached_path, duration = await client.text_to_speech(
                test_chunks[0],
                use_cache=True
            )
            
            if cached_path:
                print(f"Retrieved from cache: {cached_path} ({duration:.1f}s)")
            
            # Clean up old cache (optional)
            deleted = client.cleanup_old_cache(max_age_hours=1)
            print(f"Cleaned up {deleted} old cache files")
    
    # Run example
    asyncio.run(example())
