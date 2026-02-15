#!/usr/bin/env python3
"""
Test script for Reddit client functionality.
This script demonstrates how to use the RedditClient and tests basic functionality.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from reddit_story.reddit_client import RedditClient, RedditStory
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_reddit_client_initialization():
    """Test Reddit client initialization."""
    print("=" * 60)
    print("Testing Reddit Client Initialization")
    print("=" * 60)
    
    # Check if Reddit is configured
    if not settings.is_reddit_configured():
        print("❌ Reddit API is not configured.")
        print("   Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT")
        print("   in your .env file or environment variables.")
        print("   See .env.example for details.")
        return False
    
    print("✅ Reddit API is configured")
    print(f"   Client ID: {settings.REDDIT_CLIENT_ID[:10]}...")
    print(f"   User Agent: {settings.REDDIT_USER_AGENT}")
    
    # Test client initialization
    try:
        async with RedditClient() as client:
            print("✅ Reddit client initialized successfully")
            return True
    except Exception as e:
        print(f"❌ Failed to initialize Reddit client: {e}")
        return False

async def test_text_cleaning():
    """Test the text cleaning functionality."""
    print("\n" + "=" * 60)
    print("Testing Text Cleaning")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            "input": "Check out this [cool site](https://example.com) and visit https://google.com",
            "expected": "Check out this cool site and visit"
        },
        {
            "input": "**Bold text** and *italic text* and ~~strikethrough~~",
            "expected": "Bold text and italic text and strikethrough"
        },
        {
            "input": "EDIT: Fixed a typo\nUpdate: Added more info\nThanks for the gold!",
            "expected": ""
        },
        {
            "input": "> This is a quote\nThis is not a quote\n> Another quote",
            "expected": "This is not a quote"
        },
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        cleaned = RedditClient.clean_story_text(test_case["input"])
        passed = cleaned.strip() == test_case["expected"].strip()
        status = "✅" if passed else "❌"
        print(f"{status} Test {i}: {passed}")
        
        if not passed:
            print(f"   Input: {test_case['input']}")
            print(f"   Expected: {test_case['expected']}")
            print(f"   Got: {cleaned}")
            all_passed = False
    
    return all_passed

async def test_duration_calculation():
    """Test duration calculation."""
    print("\n" + "=" * 60)
    print("Testing Duration Calculation")
    print("=" * 60)
    
    test_cases = [
        (150, 60.0),   # 150 words = 1 minute = 60 seconds
        (300, 120.0),  # 300 words = 2 minutes = 120 seconds
        (75, 30.0),    # 75 words = 0.5 minutes = 30 seconds
    ]
    
    all_passed = True
    for word_count, expected_seconds in test_cases:
        duration = RedditClient.calculate_duration(word_count)
        passed = abs(duration - expected_seconds) < 0.1
        status = "✅" if passed else "❌"
        print(f"{status} {word_count} words -> {duration:.1f}s (expected: {expected_seconds}s)")
        
        if not passed:
            all_passed = False
    
    return all_passed

async def test_mock_fetch():
    """Test mock fetch functionality (without actual API calls)."""
    print("\n" + "=" * 60)
    print("Testing Mock Fetch (Structure Test)")
    print("=" * 60)
    
    # Create a mock story to test the data structure
    mock_story = RedditStory(
        id="test123",
        title="Test Story Title",
        text="This is a test story with some content for testing purposes.",
        subreddit="AskReddit",
        url="https://reddit.com/r/AskReddit/comments/test123",
        score=1000,
        upvote_ratio=0.95,
        created_utc=1672531200.0,
        author="test_user",
        is_nsfw=False,
        word_count=10,
        estimated_duration=4.0,
    )
    
    # Test the structure
    print("✅ RedditStory dataclass created successfully")
    print(f"   Title: {mock_story.title}")
    print(f"   Word count: {mock_story.word_count}")
    print(f"   Estimated duration: {mock_story.estimated_duration:.1f}s")
    print(f"   URL: {mock_story.url}")
    
    # Test string representation
    story_str = str(mock_story)
    assert mock_story.title in story_str
    assert mock_story.text in story_str
    print("✅ String representation works correctly")
    
    return True

async def test_with_mock_credentials():
    """Test with mock credentials to show error handling."""
    print("\n" + "=" * 60)
    print("Testing Error Handling (with invalid credentials)")
    print("=" * 60)
    
    # Create client with invalid credentials
    client = RedditClient(
        client_id="invalid_client_id",
        client_secret="invalid_client_secret",
        user_agent="Test/1.0"
    )
    
    try:
        await client.initialize()
        print("❌ Should have failed with invalid credentials")
        return False
    except Exception as e:
        print(f"✅ Correctly failed with invalid credentials: {type(e).__name__}")
        return True

async def main():
    """Run all tests."""
    print("Reddit Client Test Suite")
    print("=" * 60)
    
    tests = [
        ("Initialization", test_reddit_client_initialization),
        ("Text Cleaning", test_text_cleaning),
        ("Duration Calculation", test_duration_calculation),
        ("Mock Fetch", test_mock_fetch),
        ("Error Handling", test_with_mock_credentials),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
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
        
        # Show next steps
        if not settings.is_reddit_configured():
            print("\n⚠️  IMPORTANT: Reddit API is not fully configured.")
            print("   To use Reddit features, please:")
            print("   1. Create a Reddit app at: https://www.reddit.com/prefs/apps")
            print("   2. Choose 'script' as the application type")
            print("   3. Copy your client ID and client secret")
            print("   4. Add them to your .env file:")
            print("      REDDIT_CLIENT_ID=your_client_id")
            print("      REDDIT_CLIENT_SECRET=your_client_secret")
            print("      REDDIT_USER_AGENT=ShortsGenerator/1.0 by YourUsername")
    else:
        print("💥 SOME TESTS FAILED")
        print("\nCheck the errors above and fix them before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)