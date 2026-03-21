"""
Advanced Subtitle Generator for Shorts Videos.
Generates ASS subtitles with perfect timing, phrase-based chunking, and dynamic word highlighting.
Uses pysubs2 library for robust ASS file generation.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import pysubs2

from .models import WordTimestamp

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Phrase:
    """Represents a phrase (group of words) for subtitle display."""
    words: List[WordTimestamp]
    start_time: float
    end_time: float
    text: str
    
    @property
    def word_count(self) -> int:
        return len(self.words)

class SubtitleGenerator:
    """Generates ASS subtitles with perfect timing and dynamic highlighting."""
    
    def __init__(
        self,
        video_width: int = 1080,
        video_height: int = 1920,
        max_words_per_phrase: int = 5,
        min_words_per_phrase: int = 2,
        max_phrase_duration: float = 3.0,  # seconds
        min_gap_between_phrases: float = 0.1,  # seconds
    ):
        """
        Initialize subtitle generator.
        """
        self.video_width = video_width
        self.video_height = video_height
        self.max_words_per_phrase = max_words_per_phrase
        self.min_words_per_phrase = min_words_per_phrase
        self.max_phrase_duration = max_phrase_duration
        self.min_gap_between_phrases = min_gap_between_phrases
        
        logger.info(
            f"SubtitleGenerator initialized: "
            f"{video_width}x{video_height}, "
            f"{min_words_per_phrase}-{max_words_per_phrase} words/phrase"
        )
    
    def chunk_words_into_phrases(
        self,
        word_timestamps: List[WordTimestamp],
        audio_duration: float
    ) -> List[Phrase]:
        """
        Chunk words into phrases for optimal display.
        """
        if not word_timestamps:
            return []
        
        phrases = []
        current_phrase_words = []
        current_phrase_start = word_timestamps[0].start
        
        for i, word_ts in enumerate(word_timestamps):
            current_phrase_words.append(word_ts)
            
            should_end_phrase = False
            
            if len(current_phrase_words) >= self.max_words_per_phrase:
                should_end_phrase = True
            
            if i + 1 < len(word_timestamps):
                next_word = word_timestamps[i + 1]
                gap = next_word.start - word_ts.end
                if gap > 0.5:
                    should_end_phrase = True
            
            phrase_duration = word_ts.end - current_phrase_start
            if phrase_duration > self.max_phrase_duration:
                should_end_phrase = True
            
            if should_end_phrase and len(current_phrase_words) < self.min_words_per_phrase:
                should_end_phrase = False
            
            if should_end_phrase or i == len(word_timestamps) - 1:
                phrase_end = word_ts.end
                phrase_text = " ".join(w.word for w in current_phrase_words)
                
                phrase = Phrase(
                    words=current_phrase_words.copy(),
                    start_time=current_phrase_start,
                    end_time=phrase_end,
                    text=phrase_text
                )
                
                phrases.append(phrase)
                
                current_phrase_words = []
                if i + 1 < len(word_timestamps):
                    current_phrase_start = word_timestamps[i + 1].start
        
        phrases = self._adjust_phrase_timing(phrases, audio_duration)
        return phrases
    
    def _adjust_phrase_timing(
        self,
        phrases: List[Phrase],
        audio_duration: float,
        min_start_time: float = 0.0
    ) -> List[Phrase]:
        """
        Adjust phrase timing to ensure no overlaps and proper gaps.
        Enforces min_start_time for the first phrase.
        """
        if not phrases:
            return phrases
        
        adjusted_phrases = []
        
        for i, phrase in enumerate(phrases):
            adjusted_phrase = Phrase(
                words=phrase.words.copy(),
                start_time=phrase.start_time,
                end_time=phrase.end_time,
                text=phrase.text
            )
            
            # Ensure phrase doesn't start before 0 or min_start_time (for the first phrase)
            floor_time = min_start_time if i == 0 else 0.0
            adjusted_phrase.start_time = max(floor_time, adjusted_phrase.start_time)
            
            # Ensure phrase doesn't end after audio
            adjusted_phrase.end_time = min(audio_duration, adjusted_phrase.end_time)
            
            # Ensure minimum gap with previous phrase
            if i > 0:
                prev_phrase = adjusted_phrases[-1]
                gap = adjusted_phrase.start_time - prev_phrase.end_time
                if gap < self.min_gap_between_phrases:
                    adjusted_phrase.start_time = prev_phrase.end_time + self.min_gap_between_phrases
            
            # Ensure phrase has minimum duration
            if adjusted_phrase.end_time - adjusted_phrase.start_time < 0.3:
                adjusted_phrase.end_time = adjusted_phrase.start_time + 0.3
            
            adjusted_phrases.append(adjusted_phrase)
        
        return adjusted_phrases
    
    def _create_pysubs2_styles(self) -> Dict[str, pysubs2.SSAStyle]:
        styles = {}
        default_style = pysubs2.SSAStyle(
            fontname="Arial", fontsize=80,
            primarycolor=pysubs2.Color(255, 255, 255),
            secondarycolor=pysubs2.Color(255, 255, 255),
            outlinecolor=pysubs2.Color(0, 0, 0),
            backcolor=pysubs2.Color(0, 0, 0, 0),
            bold=True, borderstyle=1, outline=8,
            alignment=pysubs2.Alignment.MIDDLE_CENTER,
            marginv=100
        )
        styles["Default"] = default_style
        return styles
    
    def _generate_phrase_events_with_pysubs2(self, phrase: Phrase, min_start_time: float = 0.0) -> List[pysubs2.SSAEvent]:
        events = []
        min_start_ms = int(min_start_time * 1000)
        for i, current_word in enumerate(phrase.words):
            # Enforce min_start_time floor
            word_start_ms = int(current_word.start * 1000)
            word_end_ms = int(current_word.end * 1000)
            
            start_ms = max(min_start_ms, word_start_ms)
            
            if i + 1 < len(phrase.words):
                end_ms = max(min_start_ms, int(phrase.words[i + 1].start * 1000))
            else:
                end_ms = max(min_start_ms, word_end_ms)
            
            # Ensure start < end
            if start_ms >= end_ms:
                end_ms = start_ms + 100
            
            text_parts = []
            current_color = None
            for j, word in enumerate(phrase.words):
                needed_color = "\\c&H00FFFF&" if j == i else "\\c&HFFFFFF&"
                if needed_color != current_color:
                    text_parts.append("{" + needed_color + "}")
                    current_color = needed_color
                text_parts.append(word.word.upper())
                if j < len(phrase.words) - 1:
                    text_parts.append(" ")
            
            event = pysubs2.SSAEvent(
                start=start_ms, end=end_ms,
                style="Default", text="".join(text_parts)
            )
            events.append(event)
        return events
    
    def _create_pysubs2_file(self, phrases: List[Phrase], min_start_time: float = 0.0) -> pysubs2.SSAFile:
        subs = pysubs2.SSAFile()
        subs.info.update({
            "PlayResX": str(self.video_width),
            "PlayResY": str(self.video_height),
            "WrapStyle": "0",
            "ScaledBorderAndShadow": "yes",
            "ScriptType": "v4.00+",
            "YCbCr Matrix": "TV.709"
        })
        styles = self._create_pysubs2_styles()
        for name, obj in styles.items():
            subs.styles[name] = obj
        for phrase in phrases:
            is_first = (phrase == phrases[0])
            m_start = min_start_time if is_first else 0.0
            for event in self._generate_phrase_events_with_pysubs2(phrase, min_start_time=m_start):
                subs.append(event)
        return subs
    
    def generate_ass_with_pysubs2(
        self,
        word_timestamps: List[WordTimestamp],
        audio_duration: float,
        output_path: Path,
        min_start_time: float = 0.0
    ) -> bool:
        try:
            phrases = self.chunk_words_into_phrases(word_timestamps, audio_duration)
            if phrases:
                phrases = self._adjust_phrase_timing(phrases, audio_duration, min_start_time)
            if not phrases:
                return False
            subs = self._create_pysubs2_file(phrases, min_start_time=min_start_time)
            subs.save(str(output_path))
            return True
        except Exception as e:
            logger.error(f"Failed to generate ASS: {e}")
            return False
    
    def generate_ass_from_word_timestamps(
        self,
        word_timestamps: List[WordTimestamp],
        audio_duration: float,
        output_path: Path
    ) -> bool:
        return self.generate_ass_with_pysubs2(word_timestamps, audio_duration, output_path)
    
    def filter_and_adjust_timestamps(
        self,
        word_timestamps: List[WordTimestamp],
        title_word_count: int
    ) -> Tuple[List[WordTimestamp], float]:
        if title_word_count <= 0 or title_word_count >= len(word_timestamps):
            return word_timestamps, 0.0
        last_title_word = word_timestamps[title_word_count - 1]
        title_duration = last_title_word.end
        story_word_timestamps = word_timestamps[title_word_count:]
        return story_word_timestamps, title_duration
    
    def generate_ass_with_title_filter(
        self,
        word_timestamps: List[WordTimestamp],
        title_word_count: int,
        audio_duration: float,
        output_path: Path,
        min_start_time: float = 0.0
    ) -> Tuple[bool, float]:
        try:
            story_timestamps, title_duration = self.filter_and_adjust_timestamps(
                word_timestamps, title_word_count
            )
            if story_timestamps:
                story_timestamps[0].start = max(story_timestamps[0].start, min_start_time)
                if story_timestamps[0].start >= story_timestamps[0].end:
                    story_timestamps[0].end = story_timestamps[0].start + 0.1
            
            success = self.generate_ass_with_pysubs2(
                story_timestamps, audio_duration, output_path, min_start_time=min_start_time
            )
            return success, title_duration
        except Exception as e:
            logger.error(f"Failed in generate_ass_with_title_filter: {e}")
            return False, 0.0

    def generate_ass_from_text(self, text: str, audio_duration: float, output_path: Path) -> bool:
        try:
            words = text.split()
            avg = audio_duration / max(1, len(words))
            w_ts = [WordTimestamp(word=w, start=i*avg, end=(i+1)*avg, confidence=1.0) for i, w in enumerate(words)]
            return self.generate_ass_from_word_timestamps(w_ts, audio_duration, output_path)
        except Exception:
            return False
