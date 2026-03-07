"""
Story Processor for splitting Reddit stories into logical parts for Shorts videos.
Handles text segmentation, duration calculation, and part optimization.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .reddit_client import RedditStory
from config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class SplitStrategy(Enum):
    """Strategy for splitting text into parts."""
    SENTENCE = "sentence"  # Split at sentence boundaries
    PARAGRAPH = "paragraph"  # Split at paragraph boundaries
    HYBRID = "hybrid"  # Use paragraphs first, then sentences if needed

@dataclass
class StoryPart:
    """Represents a single part of a split story."""
    part_number: int
    text: str
    word_count: int
    estimated_duration: float  # in seconds
    start_index: int  # Character index in original text
    end_index: int  # Character index in original text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "part_number": self.part_number,
            "text": self.text,
            "word_count": self.word_count,
            "estimated_duration": self.estimated_duration,
            "start_index": self.start_index,
            "end_index": self.end_index,
        }

@dataclass
class ProcessedStory:
    """Represents a story that has been processed into parts."""
    story: RedditStory
    parts: List[StoryPart]
    total_parts: int
    total_duration: float
    strategy_used: SplitStrategy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "story": {
                "id": self.story.id,
                "title": self.story.title,
                "subreddit": self.story.subreddit,
                "word_count": self.story.word_count,
                "estimated_duration": self.story.estimated_duration,
            },
            "parts": [part.to_dict() for part in self.parts],
            "total_parts": self.total_parts,
            "total_duration": self.total_duration,
            "strategy_used": self.strategy_used.value,
        }

class StoryProcessor:
    """Processes stories by splitting them into logical parts for Shorts videos."""
    
    def __init__(
        self,
        min_part_duration: Optional[int] = None,
        max_part_duration: Optional[int] = None,
        words_per_minute: Optional[int] = None,
        max_parts: Optional[int] = None,
    ):
        """
        Initialize story processor with configuration.
        
        Args:
            min_part_duration: Minimum duration for each part in seconds
            max_part_duration: Maximum duration for each part in seconds
            words_per_minute: Narration speed for duration calculation
            max_parts: Maximum number of parts to create
        """
        self.min_part_duration = min_part_duration or settings.MIN_PART_DURATION
        self.max_part_duration = max_part_duration or settings.MAX_PART_DURATION
        self.words_per_minute = words_per_minute or settings.WORDS_PER_MINUTE
        self.max_parts = max_parts or settings.MAX_PARTS
        
        # Calculate word limits based on duration targets
        self.min_words_per_part = self._duration_to_words(self.min_part_duration)
        self.max_words_per_part = self._duration_to_words(self.max_part_duration)
        
        logger.info(
            f"StoryProcessor initialized: "
            f"{self.min_part_duration}-{self.max_part_duration}s parts, "
            f"{self.words_per_minute} wpm, max {self.max_parts} parts"
        )
    
    def _duration_to_words(self, duration_seconds: float) -> int:
        """Convert duration in seconds to approximate word count."""
        minutes = duration_seconds / 60
        return int(minutes * self.words_per_minute)
    
    def _words_to_duration(self, word_count: int) -> float:
        """Convert word count to estimated duration in seconds."""
        minutes = word_count / self.words_per_minute
        return minutes * 60
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using regex.
        Tries to preserve natural sentence boundaries.
        """
        # Regex to split on sentence endings (. ! ?) followed by whitespace
        # Handles common abbreviations and decimal numbers
        sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
        
        # First, normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Split into sentences
        sentences = re.split(sentence_endings, text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Handle edge cases where split didn't work well
        if not sentences:
            # Fallback: split on periods
            sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        return sentences
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs.
        """
        # Split on double newlines or multiple newlines
        paragraphs = re.split(r'\n\s*\n+', text.strip())
        
        # Filter out empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # If no paragraphs found, treat entire text as one paragraph
        if not paragraphs:
            paragraphs = [text.strip()]
        
        return paragraphs
    
    def _merge_small_segments(
        self, 
        segments: List[str], 
        start_indices: List[int]
    ) -> Tuple[List[str], List[int]]:
        """
        Merge small segments together to meet minimum word count.
        
        Args:
            segments: List of text segments
            start_indices: List of starting character indices for each segment
            
        Returns:
            Tuple of (merged_segments, merged_start_indices)
        """
        if not segments:
            return [], []
        
        merged_segments = []
        merged_indices = []
        
        current_segment = segments[0]
        current_start = start_indices[0]
        current_word_count = len(current_segment.split())
        
        for i in range(1, len(segments)):
            segment = segments[i]
            segment_word_count = len(segment.split())
            
            # Check if merging would keep us under max limit
            if current_word_count + segment_word_count <= self.max_words_per_part:
                # Merge this segment
                current_segment += " " + segment
                current_word_count += segment_word_count
            else:
                # Current segment is complete, start new one
                merged_segments.append(current_segment)
                merged_indices.append(current_start)
                
                current_segment = segment
                current_start = start_indices[i]
                current_word_count = segment_word_count
        
        # Add the last segment
        merged_segments.append(current_segment)
        merged_indices.append(current_start)
        
        return merged_segments, merged_indices
    
    def _split_large_segments(
        self, 
        segments: List[str], 
        start_indices: List[int]
    ) -> Tuple[List[str], List[int]]:
        """
        Split large segments that exceed maximum word count.
        
        Args:
            segments: List of text segments
            start_indices: List of starting character indices for each segment
            
        Returns:
            Tuple of (split_segments, split_start_indices)
        """
        if not segments:
            return [], []
        
        split_segments = []
        split_indices = []
        
        for segment, start_index in zip(segments, start_indices):
            word_count = len(segment.split())
            
            if word_count <= self.max_words_per_part:
                # Segment is within limits, keep as-is
                split_segments.append(segment)
                split_indices.append(start_index)
            else:
                # Segment is too large, split into sentences
                sentences = self._split_into_sentences(segment)
                sentence_indices = []
                
                # Calculate start indices for each sentence
                current_pos = 0
                for sentence in sentences:
                    sentence_indices.append(start_index + current_pos)
                    current_pos += len(sentence) + 1  # +1 for space
                
                # Merge sentences into appropriate-sized chunks
                merged_sentences, merged_indices = self._merge_small_segments(
                    sentences, sentence_indices
                )
                
                split_segments.extend(merged_sentences)
                split_indices.extend(merged_indices)
        
        return split_segments, split_indices
    
    def _create_story_parts(
        self, 
        segments: List[str], 
        start_indices: List[int]
    ) -> List[StoryPart]:
        """
        Create StoryPart objects from text segments.
        
        Args:
            segments: List of text segments
            start_indices: List of starting character indices
            
        Returns:
            List of StoryPart objects
        """
        parts = []
        
        for i, (segment, start_index) in enumerate(zip(segments, start_indices), 1):
            word_count = len(segment.split())
            duration = self._words_to_duration(word_count)
            
            # Calculate end index
            end_index = start_index + len(segment)
            
            part = StoryPart(
                part_number=i,
                text=segment,
                word_count=word_count,
                estimated_duration=duration,
                start_index=start_index,
                end_index=end_index,
            )
            
            parts.append(part)
        
        return parts
    
    def process_story(
        self,
        story: RedditStory,
        strategy: SplitStrategy = SplitStrategy.HYBRID,
        split_into_parts: bool = True
    ) -> ProcessedStory:
        """
        Process a Reddit story by splitting it into logical parts.

        Args:
            story: RedditStory object to process
            strategy: Splitting strategy to use
            split_into_parts: Whether to split the story into multiple parts

        Returns:
            ProcessedStory object with parts
        """
        logger.info(
            f"Processing story: '{story.title[:50]}...' "
            f"({story.word_count} words, {story.estimated_duration:.1f}s)"
        )

        # Evaluate whether to split
        should_split = split_into_parts and story.estimated_duration > 180.0
        
        if not should_split:
            logger.info(
                f"Story duration ({story.estimated_duration:.1f}s) <= 180s or split_into_parts=False. "
                f"Returning single part."
            )
            
            # Create a single StoryPart with the entire text
            text = story.text
            word_count = len(text.split())
            duration = story.estimated_duration
            
            single_part = StoryPart(
                part_number=1,
                text=text,
                word_count=word_count,
                estimated_duration=duration,
                start_index=0,
                end_index=len(text),
            )
            
            processed_story = ProcessedStory(
                story=story,
                parts=[single_part],
                total_parts=1,
                total_duration=duration,
                strategy_used=strategy,
            )
            
            logger.info(
                f"Story processed as single part, duration: {duration:.1f}s"
            )
            
            return processed_story

        # Use only story text (title is handled separately in audio generation pipeline)
        text = story.text
        original_length = len(text)

        # Step 1: Initial segmentation based on strategy
        if strategy == SplitStrategy.PARAGRAPH:
            segments = self._split_into_paragraphs(text)
        elif strategy == SplitStrategy.SENTENCE:
            segments = self._split_into_sentences(text)
        else:  # HYBRID - start with paragraphs
            segments = self._split_into_paragraphs(text)

        # Calculate start indices for each segment
        start_indices = []
        current_pos = 0
        for segment in segments:
            # Find the segment in the original text
            index = text.find(segment, current_pos)
            if index == -1:
                index = current_pos
            start_indices.append(index)
            current_pos = index + len(segment)

        # Step 2: Merge small segments
        segments, start_indices = self._merge_small_segments(segments, start_indices)

        # Step 3: Split large segments
        segments, start_indices = self._split_large_segments(segments, start_indices)

        # Step 4: Apply max parts limit
        if len(segments) > self.max_parts:
            logger.warning(
                f"Story has {len(segments)} parts, limiting to {self.max_parts}"
            )
            segments = segments[:self.max_parts]
            start_indices = start_indices[:self.max_parts]

        # Step 5: Create StoryPart objects
        parts = self._create_story_parts(segments, start_indices)

        # Step 6: Calculate totals
        total_duration = sum(part.estimated_duration for part in parts)

        # Verify we processed the entire text
        processed_length = sum(len(part.text) for part in parts)
        if processed_length < original_length * 0.9:  # Allow 10% difference for whitespace
            logger.warning(
                f"Processed text length ({processed_length}) is significantly "
                f"less than original ({original_length})"
            )

        processed_story = ProcessedStory(
            story=story,
            parts=parts,
            total_parts=len(parts),
            total_duration=total_duration,
            strategy_used=strategy,
        )

        logger.info(
            f"Story processed into {len(parts)} parts, "
            f"total duration: {total_duration:.1f}s"
        )

        for i, part in enumerate(parts, 1):
            logger.debug(
                f"  Part {i}: {part.word_count} words, "
                f"{part.estimated_duration:.1f}s, "
                f"text: '{part.text[:50]}...'"
            )

        return processed_story
    
    def validate_parts(self, processed_story: ProcessedStory) -> bool:
        """
        Validate that all parts meet the duration constraints.
        
        Args:
            processed_story: ProcessedStory to validate
            
        Returns:
            True if all parts are valid, False otherwise
        """
        all_valid = True
        
        for part in processed_story.parts:
            if part.estimated_duration < self.min_part_duration:
                logger.warning(
                    f"Part {part.part_number} is too short: "
                    f"{part.estimated_duration:.1f}s < {self.min_part_duration}s"
                )
                all_valid = False
            
            if part.estimated_duration > self.max_part_duration:
                logger.warning(
                    f"Part {part.part_number} is too long: "
                    f"{part.estimated_duration:.1f}s > {self.max_part_duration}s"
                )
                all_valid = False
        
        return all_valid


# Utility functions for direct use
def process_story(
    story: RedditStory, 
    strategy: SplitStrategy = SplitStrategy.HYBRID,
    **kwargs
) -> ProcessedStory:
    """
    Convenience function to process a story.
    
    Args:
        story: RedditStory to process
        strategy: Splitting strategy
        **kwargs: Additional arguments for StoryProcessor
        
    Returns:
        ProcessedStory object
    """
    processor = StoryProcessor(**kwargs)
    return processor.process_story(story, strategy)


# Example usage
if __name__ == "__main__":
    import asyncio
    from reddit_client import RedditClient
    
    async def example():
        # Create a mock story for testing
        mock_story = RedditStory(
            id="test123",
            title="Test Story About Programming",
            text="""Hello everyone. This is a test story about programming and software development.
            
            Programming is the process of writing instructions for computers to execute. These instructions are written in programming languages like Python, JavaScript, and Java.
            
            Software development involves designing, coding, testing, and maintaining applications. It requires problem-solving skills and attention to detail.
            
            Good programmers write clean, readable code that others can understand. They also document their work and write tests to ensure quality.
            
            Learning to program takes time and practice. Start with simple projects and gradually tackle more complex challenges. Don't be afraid to make mistakes - that's how you learn!
            
            Remember: The best way to learn programming is by doing. Build projects, contribute to open source, and never stop learning.""",
            subreddit="AskReddit",
            url="https://reddit.com/test",
            score=100,
            upvote_ratio=0.95,
            created_utc=1672531200.0,
            author="test_user",
            is_nsfw=False,
            word_count=150,
            estimated_duration=60.0,
        )
        
        # Process the story
        processor = StoryProcessor()
        processed = processor.process_story(mock_story)
        
        print(f"Original story: {mock_story.word_count} words")
        print(f"Split into {processed.total_parts} parts")
        print(f"Total duration: {processed.total_duration:.1f}s")
        print()
        
        for part in processed.parts:
            print(f"Part {part.part_number}:")
            print(f"  Words: {part.word_count}")
            print(f"  Duration: {part.estimated_duration:.1f}s")
            print(f"  Text: '{part.text[:80]}...'")
            print()
        
        # Validate parts
        is_valid = processor.validate_parts(processed)
        print(f"All parts valid: {is_valid}")
    
    # Run example
    asyncio.run(example())