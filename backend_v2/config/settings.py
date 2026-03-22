"""
Configuration management for the ShortsGenerator application.
Handles environment variables, default values, and validation.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    Uses pydantic for validation and type conversion.
    """
    
    # Application
    APP_NAME: str = "ShortsGenerator Backend v2"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    
    # File paths
    BASE_DIR: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    DATA_DIR: Path = BASE_DIR / "data"
    CACHE_DIR: Path = BASE_DIR / "cache"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    BACKGROUNDS_DIR: Path = ASSETS_DIR / "backgrounds"
    DEFAULT_BGM_PATH: Path = ASSETS_DIR / "audio" / "lofi_bg.mp3"
    
    # File upload settings
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: Union[str, List[str]] = [".mp4", ".avi", ".mkv", ".mov", ".webm"]
    
    # Reddit Settings (using public JSON endpoints - no API keys required)
    REDDIT_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Reddit story settings
    DEFAULT_SUBREDDIT: str = "AskReddit"
    DEFAULT_TIME_FILTER: str = "day"  # hour, day, week, month, year, all
    MIN_STORY_SCORE: int = 100
    MIN_STORY_LENGTH: int = 200  # characters
    MAX_STORY_LENGTH: int = 5000  # characters
    EXCLUDE_NSFW: bool = True
    WORDS_PER_MINUTE: int = 180  # Narration speed
    
    # ElevenLabs API Settings (for Phase 2)
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_RACHEL: str = "21m00Tcm4TlvDq8ikWAM"
    ELEVENLABS_VOICE_ADAM: str = "pNInz6obpgDQGcFmaJgB"
    ELEVENLABS_VOICE_ELLI: str = "MF3mGyEYCl7XYWbV9V6O"
    ELEVENLABS_VOICE_JOSH: str = "TxGEqnHWrfWFTfGW9XjX"
    
    # Gemini settings for keyword extraction (optional)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-flash-latest"
    
    # Edge TTS Voices (for TTS_ENGINE = "edge")
    EDGE_TTS_VOICE_FEMALE: str = "en-US-JennyNeural"
    EDGE_TTS_VOICE_MALE: str = "en-US-ChristopherNeural"
    
    DEFAULT_VOICE_ID: str = EDGE_TTS_VOICE_MALE
    
    EDGE_TTS_ALIASES: Dict[str, str] = Field(
        default_factory=lambda: {
            "female": "en-US-JennyNeural",
            "male": "en-US-ChristopherNeural", 
            "aria": "en-US-AriaNeural",
            "christopher": "en-US-ChristopherNeural",
            "default": "en-US-JennyNeural",
        }
    )
    
    TTS_ENGINE: str = "edge"
    
    # Background video settings
    DEFAULT_BACKGROUND_THEME: str = "minecraft"
    BACKGROUND_THEMES: List[str] = ["abstract", "food", "gta", "lofi", "minecraft", "nature", "oddly satisfying", "subway surfer"]
    MIN_BACKGROUND_DURATION: int = 60
    MAX_BACKGROUND_DURATION: int = 300
    
    # Dynamic background clip settings
    BACKGROUND_CLIP_DURATION_MIN: float = 5.0
    BACKGROUND_CLIP_DURATION_MAX: float = 10.0
    BACKGROUND_DYNAMIC_SWITCHING: bool = True
    BGM_VOLUME_DELTA: float = -10.0
    
    # Video processing
    TARGET_WIDTH: int = 1080
    TARGET_HEIGHT: int = 1920
    TARGET_FPS: int = 30
    VIDEO_CRF: int = 23
    VIDEO_PRESET: str = "veryfast"
    AUDIO_BITRATE: str = "128k"
    FINAL_VIDEO_SPEED: float = 1.2
    
    # Story segmentation
    MIN_PART_DURATION: int = 30
    MAX_PART_DURATION: int = 60
    MAX_PARTS: int = 5
    
    # Caching
    CACHE_TTL: int = 3600
    ENABLE_CACHE: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @validator("TTS_ENGINE")
    def validate_tts_engine(cls, v):
        if v.lower() not in ["edge", "elevenlabs"]:
            raise ValueError(f"Invalid TTS engine: {v}. Must be 'edge' or 'elevenlabs'")
        return v.lower()

    @validator("ASSETS_DIR", "BACKGROUNDS_DIR", pre=True)
    def resolve_relative_to_base_dir(cls, v: Any, values: Dict[str, Any]) -> Any:
        if isinstance(v, str): v = Path(v)
        if isinstance(v, Path) and not v.is_absolute():
            if "BASE_DIR" in values and values["BASE_DIR"]:
                v = values["BASE_DIR"] / v
            else: v = v.absolute()
        return v
    
    @validator("UPLOAD_DIR", "OUTPUT_DIR", "DATA_DIR", "CACHE_DIR", "ASSETS_DIR", "BACKGROUNDS_DIR", pre=True)
    def validate_and_create_dirs(cls, v: Path) -> Path:
        if isinstance(v, str): v = Path(v)
        if not v.is_absolute(): v = v.absolute()
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    def is_reddit_configured(self) -> bool: return True
    def is_elevenlabs_configured(self) -> bool: return bool(self.ELEVENLABS_API_KEY)
    
    @property
    def use_gemini_keywords(self) -> bool:
        return bool(self.GEMINI_API_KEY)
    
    def get_voice_id(self, voice_name: Optional[str] = None, engine: Optional[str] = None) -> str:
        engine = engine or self.TTS_ENGINE.lower()
        if engine == "edge":
            if voice_name:
                voice_lower = voice_name.lower()
                if voice_lower in self.EDGE_TTS_ALIASES: return self.EDGE_TTS_ALIASES[voice_lower]
                elif "neural" in voice_lower or "en-" in voice_lower: return voice_name
            return self.DEFAULT_VOICE_ID
        elif engine == "elevenlabs":
            evm = {"rachel": self.ELEVENLABS_VOICE_RACHEL, "adam": self.ELEVENLABS_VOICE_ADAM, "elli": self.ELEVENLABS_VOICE_ELLI, "josh": self.ELEVENLABS_VOICE_JOSH}
            if voice_name:
                voice_lower = voice_name.lower()
                if voice_lower in evm: return evm[voice_lower]
                if len(voice_name) == 20 and voice_name.isalnum(): return voice_name
            return self.ELEVENLABS_VOICE_ADAM
        return self.DEFAULT_VOICE_ID

settings = Settings()
