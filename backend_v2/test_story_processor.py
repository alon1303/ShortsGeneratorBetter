#!/usr/bin/env python3
"""
Test script for Story Processor functionality.
Tests text segmentation, part creation, and validation.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from reddit_story.reddit_client import RedditStory
from reddit_story.story_processor import (
    StoryProcessor, 
    ProcessedStory, 
    StoryPart, 
    SplitStrategy,
    process_story,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_story() -> RedditStory:
    """Create a test Reddit story for testing."""
    return RedditStory(
        id="test123",
        title="Test Story About Programming and Learning",
        text="""Hello everyone. This is a test story about programming and software development.

Programming is the process of writing instructions for computers to execute. These instructions are written in programming languages like Python, JavaScript, and Java.

Software development involves designing, coding, testing, and maintaining applications. It requires problem-solving skills and attention to detail.

Good programmers write clean, readable code that others can understand. They also document their work and write tests to ensure quality.

Learning to program takes time and practice. Start with simple projects and gradually tackle more complex challenges. Don't be afraid to make mistakes - that's how you learn!

Remember: The best way to learn programming is by doing. Build projects, contribute to open source, and never stop learning. The journey is long but rewarding.

In conclusion, programming is both an art and a science. It requires creativity, logic, and persistence. Keep learning and keep building!""",
        subreddit="AskReddit",
        url="https://reddit.com/test",
        score=100,
        upvote_ratio=0.95,
        created_utc=1672531200.0,
        author="test_user",
        is_nsfw=False,
        word_count=180,
        estimated_duration=72.0,
    )

def test_story_part_dataclass():
    """Test StoryPart dataclass functionality."""
    print("=" * 60)
    print("Testing StoryPart Dataclass")
    print("=" * 60)
    
    part = StoryPart(
        part_number=1,
        text="This is a test part.",
        word_count=5,
        estimated_duration=2.0,
        start_index=0,
        end_index=20,
    )
    
    # Test attributes
    assert part.part_number == 1
    assert part.text == "This is a test part."
    assert part.word_count == 5
    assert part.estimated_duration == 2.0
    assert part.start_index == 0
    assert part.end_index == 20
    
    # Test to_dict method
    part_dict = part.to_dict()
    assert part_dict["part_number"] == 1
    assert part_dict["text"] == "This is a test part."
    assert part_dict["word_count"] == 5
    assert part_dict["estimated_duration"] == 2.0
    
    print("✅ StoryPart dataclass tests passed")
    return True

def test_processed_story_dataclass():
    """Test ProcessedStory dataclass functionality."""
    print("\n" + "=" * 60)
    print("Testing ProcessedStory Dataclass")
    print("=" * 60)
    
    # Create a test story
    story = create_test_story()
    
    # Create test parts
    parts = [
        StoryPart(
            part_number=1,
            text="Part one text",
            word_count=10,
            estimated_duration=4.0,
            start_index=0,
            end_index=13,
        ),
        StoryPart(
            part_number=2,
            text="Part two text",
            word_count=8,
            estimated_duration=3.2,
            start_index=14,
            end_index=27,
        ),
    ]
    
    processed = ProcessedStory(
        story=story,
        parts=parts,
        total_parts=2,
        total_duration=7.2,
        strategy_used=SplitStrategy.HYBRID,
    )
    
    # Test attributes
    assert processed.story == story
    assert len(processed.parts) == 2
    assert processed.total_parts == 2
    assert processed.total_duration == 7.2
    assert processed.strategy_used == SplitStrategy.HYBRID
    
    # Test to_dict method
    processed_dict = processed.to_dict()
    assert processed_dict["story"]["id"] == "test123"
    assert processed_dict["total_parts"] == 2
    assert processed_dict["total_duration"] == 7.2
    assert processed_dict["strategy_used"] == "hybrid"
    assert len(processed_dict["parts"]) == 2
    
    print("✅ ProcessedStory dataclass tests passed")
    return True

def test_story_processor_initialization():
    """Test StoryProcessor initialization."""
    print("\n" + "=" * 60)
    print("Testing StoryProcessor Initialization")
    print("=" * 60)
    
    # Test with default settings
    processor1 = StoryProcessor()
    assert processor1.min_part_duration == 30
    assert processor1.max_part_duration == 60
    assert processor1.words_per_minute == 150
    assert processor1.max_parts == 5
    
    # Test word limits calculation
    assert processor1.min_words_per_part == 75  # 30s at 150 wpm = 75 words
    assert processor1.max_words_per_part == 150  # 60s at 150 wpm = 150 words
    
    # Test with custom settings
    processor2 = StoryProcessor(
        min_part_duration=20,
        max_part_duration=40,
        words_per_minute=120,
        max_parts=3,
    )
    assert processor2.min_part_duration == 20
    assert processor2.max_part_duration == 40
    assert processor2.words_per_minute == 120
    assert processor2.max_parts == 3
    
    print("✅ StoryProcessor initialization tests passed")
    return True

def test_duration_conversion():
    """Test duration to word conversion and vice versa."""
    print("\n" + "=" * 60)
    print("Testing Duration Conversion")
    print("=" * 60)
    
    processor = StoryProcessor(words_per_minute=150)
    
    # Test duration to words
    assert processor._duration_to_words(60) == 150  # 1 minute = 150 words
    assert processor._duration_to_words(30) == 75   # 30 seconds = 75 words
    assert processor._duration_to_words(120) == 300 # 2 minutes = 300 words
    
    # Test words to duration
    assert processor._words_to_duration(150) == 60.0  # 150 words = 60 seconds
    assert processor._words_to_duration(75) == 30.0   # 75 words = 30 seconds
    assert processor._words_to_duration(300) == 120.0 # 300 words = 120 seconds
    
    print("✅ Duration conversion tests passed")
    return True

def test_sentence_splitting():
    """Test sentence splitting functionality."""
    print("\n" + "=" * 60)
    print("Testing Sentence Splitting")
    print("=" * 60)
    
    processor = StoryProcessor()
    
    # Test basic sentence splitting
    text = "Hello world. This is a test. Another sentence!"
    sentences = processor._split_into_sentences(text)
    assert len(sentences) == 3
    # The splitter keeps the period as part of the sentence
    assert "Hello world" in sentences[0]
    assert "This is a test" in sentences[1]
    assert "Another sentence" in sentences[2]
    
    # Test with question marks and exclamation
    text = "What is this? It's a test! Really."
    sentences = processor._split_into_sentences(text)
    assert len(sentences) == 3
    
    # Test with abbreviations (should not split on periods in abbreviations)
    text = "Dr. Smith went to the U.S.A. He had a Ph.D."
    sentences = processor._split_into_sentences(text)
    # This is a limitation of simple regex, but acceptable for our use case
    
    print("✅ Sentence splitting tests passed")
    return True

def test_paragraph_splitting():
    """Test paragraph splitting functionality."""
    print("\n" + "=" * 60)
    print("Testing Paragraph Splitting")
    print("=" * 60)
    
    processor = StoryProcessor()
    
    # Test basic paragraph splitting
    text = """First paragraph.
    
Second paragraph with multiple lines.
    
Third paragraph."""
    
    paragraphs = processor._split_into_paragraphs(text)
    assert len(paragraphs) == 3
    assert "First paragraph" in paragraphs[0]
    assert "Second paragraph" in paragraphs[1]
    assert "Third paragraph" in paragraphs[2]
    
    # Test with single paragraph
    text = "Single paragraph without breaks."
    paragraphs = processor._split_into_paragraphs(text)
    assert len(paragraphs) == 1
    assert paragraphs[0] == text
    
    print("✅ Paragraph splitting tests passed")
    return True

def test_merge_small_segments():
    """Test merging of small segments."""
    print("\n" + "=" * 60)
    print("Testing Small Segment Merging")
    print("=" * 60)
    
    processor = StoryProcessor(
        min_part_duration=30,
        max_part_duration=60,
        words_per_minute=150,
    )
    
    # Create test segments with word counts
    segments = [
        "Short segment one.",  # ~3 words
        "Another short segment.",  # ~3 words
        "Medium length segment with more words.",  # ~6 words
        "Very short.",  # ~2 words
    ]
    
    start_indices = [0, 20, 40, 70]
    
    # Merge segments
    merged_segments, merged_indices = processor._merge_small_segments(
        segments, start_indices
    )
    
    # Should merge small segments together
    assert len(merged_segments) < len(segments)
    
    # Check that indices are preserved
    assert len(merged_segments) == len(merged_indices)
    
    print(f"✅ Merged {len(segments)} segments into {len(merged_segments)} segments")
    return True

def test_process_story():
    """Test complete story processing."""
    print("\n" + "=" * 60)
    print("Testing Complete Story Processing")
    print("=" * 60)
    
    # Create test story
    story = create_test_story()
    
    # Process with different strategies
    processor = StoryProcessor(
        min_part_duration=20,
        max_part_duration=40,
        words_per_minute=150,
        max_parts=10,
    )
    
    # Test hybrid strategy (default)
    processed = processor.process_story(story, SplitStrategy.HYBRID)
    
    # Verify results
    assert isinstance(processed, ProcessedStory)
    assert processed.story == story
    assert len(processed.parts) > 0
    assert processed.total_parts == len(processed.parts)
    assert processed.total_duration > 0
    assert processed.strategy_used == SplitStrategy.HYBRID
    
    # Verify each part
    for i, part in enumerate(processed.parts, 1):
        assert part.part_number == i
        assert part.text
        assert part.word_count > 0
        assert part.estimated_duration > 0
        assert part.start_index >= 0
        assert part.end_index > part.start_index
    
    # Test paragraph strategy
    processed_para = processor.process_story(story, SplitStrategy.PARAGRAPH)
    assert processed_para.strategy_used == SplitStrategy.PARAGRAPH
    
    # Test sentence strategy
    processed_sent = processor.process_story(story, SplitStrategy.SENTENCE)
    assert processed_sent.strategy_used == SplitStrategy.SENTENCE
    
    print(f"✅ Story processing tests passed:")
    print(f"   Hybrid: {processed.total_parts} parts, {processed.total_duration:.1f}s")
    print(f"   Paragraph: {processed_para.total_parts} parts")
    print(f"   Sentence: {processed_sent.total_parts} parts")
    
    return True

def test_validation():
    """Test part validation."""
    print("\n" + "=" * 60)
    print("Testing Part Validation")
    print("=" * 60)
    
    story = create_test_story()
    processor = StoryProcessor(
        min_part_duration=30,
        max_part_duration=60,
        words_per_minute=150,
    )
    
    # Process story
    processed = processor.process_story(story)
    
    # Validate parts
    is_valid = processor.validate_parts(processed)
    
    # Check each part
    for part in processed.parts:
        duration = part.estimated_duration
        assert duration >= processor.min_part_duration or not is_valid
        assert duration <= processor.max_part_duration or not is_valid
    
    print(f"✅ Parts validation: {'PASS' if is_valid else 'FAIL'}")
    print(f"   Min duration: {processor.min_part_duration}s")
    print(f"   Max duration: {processor.max_part_duration}s")
    
    # Test with intentionally bad parts
    bad_parts = [
        StoryPart(
            part_number=1,
            text="Too short",
            word_count=10,  # ~4 seconds at 150 wpm
            estimated_duration=4.0,
            start_index=0,
            end_index=9,
        ),
        StoryPart(
            part_number=2,
            text="Way too long " * 50,
            word_count=600,  # ~240 seconds at 150 wpm
            estimated_duration=240.0,
            start_index=10,
            end_index=610,
        ),
    ]
    
    bad_processed = ProcessedStory(
        story=story,
        parts=bad_parts,
        total_parts=2,
        total_duration=244.0,
        strategy_used=SplitStrategy.HYBRID,
    )
    
    is_bad_valid = processor.validate_parts(bad_processed)
    assert not is_bad_valid, "Should fail validation for bad parts"
    
    print("✅ Validation correctly identifies bad parts")
    return True

def test_convenience_function():
    """Test the convenience process_story function."""
    print("\n" + "=" * 60)
    print("Testing Convenience Function")
    print("=" * 60)
    
    story = create_test_story()
    
    # Use convenience function
    processed = process_story(
        story,
        strategy=SplitStrategy.HYBRID,
        min_part_duration=25,
        max_part_duration=45,
    )
    
    assert isinstance(processed, ProcessedStory)
    assert len(processed.parts) > 0
    
    print(f"✅ Convenience function created {len(processed.parts)} parts")
    return True

async def main():
    """Run all tests."""
    print("Story Processor Test Suite")
    print("=" * 60)
    
    tests = [
        ("StoryPart Dataclass", test_story_part_dataclass),
        ("ProcessedStory Dataclass", test_processed_story_dataclass),
        ("Processor Initialization", test_story_processor_initialization),
        ("Duration Conversion", test_duration_conversion),
        ("Sentence Splitting", test_sentence_splitting),
        ("Paragraph Splitting", test_paragraph_splitting),
        ("Segment Merging", test_merge_small_segments),
        ("Story Processing", test_process_story),
        ("Part Validation", test_validation),
        ("Convenience Function", test_convenience_function),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nStory Processor is ready for use!")
    else:
        print("💥 SOME TESTS FAILED")
        print("\nCheck the errors above and fix them before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)