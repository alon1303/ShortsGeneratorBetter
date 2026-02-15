#!/usr/bin/env python3
"""
Test script for ElevenLabs Client functionality.
Tests TTS client structure, caching, and error handling.
"""

import asyncio
import logging
import sys
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from reddit_story.elevenlabs_client import (
    ElevenLabsClient, 
    AudioChunk,
    generate_story_audio,
)
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_audio_chunk_dataclass():
    """Test AudioChunk dataclass functionality."""
    print("=" * 60)
    print("Testing AudioChunk Dataclass")
    print("=" * 60)
    
    # Create test audio chunk
    chunk = AudioChunk(
        chunk_id="test123",
        text="This is a test audio chunk.",
        audio_path=Path("/tmp/test.mp3"),
        duration_seconds=5.5,
        voice_id="voice_123",
        file_size_bytes=1024,
    )
    
    # Test attributes
    assert chunk.chunk_id == "test123"
    assert chunk.text == "This is a test audio chunk."
    assert chunk.audio_path == Path("/tmp/test.mp3")
    assert chunk.duration_seconds == 5.5
    assert chunk.voice_id == "voice_123"
    assert chunk.file_size_bytes == 1024
    
    # Test to_dict method
    chunk_dict = chunk.to_dict()
    assert chunk_dict["chunk_id"] == "test123"
    assert "This is a test audio chunk." in chunk_dict["text"]
    assert chunk_dict["duration_seconds"] == 5.5
    assert chunk_dict["voice_id"] == "voice_123"
    assert chunk_dict["file_size_bytes"] == 1024
    
    print("✅ AudioChunk dataclass tests passed")
    return True

def test_client_initialization():
    """Test ElevenLabsClient initialization."""
    print("\n" + "=" * 60)
    print("Testing ElevenLabsClient Initialization")
    print("=" * 60)
    
    # Test with default settings
    client1 = ElevenLabsClient()
    assert client1.default_voice_id == settings.DEFAULT_VOICE_ID
    assert client1.timeout == 30
    assert client1.cache_dir.exists()
    assert client1.voices_dir.exists()
    
    # Test with custom settings
    client2 = ElevenLabsClient(
        api_key="test_key",
        voice_id="custom_voice",
        timeout=60,
        cache_dir=Path("/tmp/test_cache"),
    )
    assert client2.api_key == "test_key"
    assert client2.default_voice_id == "custom_voice"
    assert client2.timeout == 60
    
    print("✅ ElevenLabsClient initialization tests passed")
    return True

def test_cache_key_generation():
    """Test cache key generation."""
    print("\n" + "=" * 60)
    print("Testing Cache Key Generation")
    print("=" * 60)
    
    client = ElevenLabsClient()
    
    # Generate cache keys
    key1 = client._generate_cache_key("Hello world", "voice_123")
    key2 = client._generate_cache_key("Hello world", "voice_123")
    key3 = client._generate_cache_key("Different text", "voice_123")
    key4 = client._generate_cache_key("Hello world", "voice_456")
    
    # Same text and voice should produce same key
    assert key1 == key2
    
    # Different text or voice should produce different keys
    assert key1 != key3
    assert key1 != key4
    
    # Keys should be 32-character hex strings (MD5)
    assert len(key1) == 32
    assert all(c in "0123456789abcdef" for c in key1)
    
    print("✅ Cache key generation tests passed")
    return True

@patch('aiohttp.ClientSession')
async def test_text_to_speech_mock(mock_session_class):
    """Test text_to_speech with mocked API."""
    print("\n" + "=" * 60)
    print("Testing Text-to-Speech (Mocked)")
    print("=" * 60)
    
    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=b"fake audio data")
    
    # Create mock session
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session_class.return_value = mock_session
    
    # Create client with test API key
    client = ElevenLabsClient(api_key="test_key")
    
    # Mock the session creation
    client._session = mock_session
    
    # Test text_to_speech
    audio_path, duration = await client.text_to_speech(
        "Hello world",
        voice_id="test_voice",
        use_cache=False,  # Don't use cache for this test
    )
    
    # Verify the API was called
    mock_session.post.assert_called_once()
    
    # Since we're mocking, audio_path should be None or a Path
    # and duration should be 0.0 or a positive number
    
    print("✅ Text-to-speech mock test passed")
    return True

async def test_generate_audio_chunks_mock():
    """Test generate_audio_chunks with mocked API."""
    print("\n" + "=" * 60)
    print("Testing Generate Audio Chunks (Mocked)")
    print("=" * 60)
    
    # Create test text chunks
    text_chunks = [
        "First chunk of text.",
        "Second chunk with more words.",
        "Third and final chunk.",
    ]
    
    # Create client
    client = ElevenLabsClient(api_key="test_key")
    
    # Mock the text_to_speech method
    with patch.object(client, 'text_to_speech', new_callable=AsyncMock) as mock_tts:
        # Create mock Path objects with mocked stat() method
        mock_path1 = MagicMock(spec=Path)
        mock_path1.stat.return_value.st_size = 1024
        
        mock_path2 = MagicMock(spec=Path)
        mock_path2.stat.return_value.st_size = 2048
        
        mock_path3 = MagicMock(spec=Path)
        mock_path3.stat.return_value.st_size = 1536
        
        # Set up mock to return fake audio paths
        mock_tts.side_effect = [
            (mock_path1, 4.5),
            (mock_path2, 5.2),
            (mock_path3, 3.8),
        ]
        
        # Generate audio chunks
        audio_chunks = await client.generate_audio_chunks(text_chunks)
        
        # Verify results
        assert len(audio_chunks) == 3
        assert audio_chunks[0].text == text_chunks[0]
        assert audio_chunks[1].text == text_chunks[1]
        assert audio_chunks[2].text == text_chunks[2]
        
        # Verify text_to_speech was called for each chunk
        assert mock_tts.call_count == 3
    
    print("✅ Generate audio chunks mock test passed")
    return True

async def test_error_handling():
    """Test error handling in TTS requests."""
    print("\n" + "=" * 60)
    print("Testing Error Handling")
    print("=" * 60)
    
    # Test 1: No API key
    client1 = ElevenLabsClient(api_key=None)
    audio_path, duration = await client1.text_to_speech("Test")
    assert audio_path is None
    assert duration == 0.0
    
    # Test 2: Mock API error
    client2 = ElevenLabsClient(api_key="test_key")
    
    with patch.object(client2, '_get_session', new_callable=AsyncMock) as mock_get_session:
        # Create mock session that raises an exception
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=Exception("API error"))
        mock_get_session.return_value = mock_session
        
        audio_path, duration = await client2.text_to_speech("Test", use_cache=False)
        assert audio_path is None
        assert duration == 0.0
    
    print("✅ Error handling tests passed")
    return True

def test_cache_cleanup():
    """Test cache cleanup functionality."""
    print("\n" + "=" * 60)
    print("Testing Cache Cleanup")
    print("=" * 60)
    
    # Create client with a temporary cache directory
    import tempfile
    import time
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_cache = Path(temp_dir) / "cache"
        client = ElevenLabsClient(cache_dir=temp_cache)
        
        # Create some test files in the cache
        old_file = client.voices_dir / "old_file.mp3"
        new_file = client.voices_dir / "new_file.mp3"
        
        # Write test content
        old_file.write_text("old audio data")
        new_file.write_text("new audio data")
        
        # Set file modification times
        current_time = time.time()
        old_time = current_time - 7200  # 2 hours ago
        new_time = current_time - 1800  # 30 minutes ago
        
        os.utime(old_file, (old_time, old_time))
        os.utime(new_file, (new_time, new_time))
        
        # Create metadata files
        old_meta = old_file.with_suffix('.json')
        new_meta = new_file.with_suffix('.json')
        
        old_meta.write_text('{"timestamp": 1000}')
        new_meta.write_text('{"timestamp": 2000}')
        
        # Clean up files older than 1 hour
        deleted_count = client.cleanup_old_cache(max_age_hours=1)
        
        # Only the old file (2 hours old) should be deleted
        # The new file (30 minutes old) should remain
        assert deleted_count == 1
        assert not old_file.exists()
        assert not old_meta.exists()
        assert new_file.exists()
        assert new_meta.exists()
    
    print("✅ Cache cleanup tests passed")
    return True

async def test_convenience_function():
    """Test the convenience generate_story_audio function."""
    print("\n" + "=" * 60)
    print("Testing Convenience Function")
    print("=" * 60)
    
    text_chunks = ["Test chunk 1", "Test chunk 2"]
    
    # Mock the ElevenLabsClient context manager
    with patch('reddit_story.elevenlabs_client.ElevenLabsClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock generate_audio_chunks
        mock_audio_chunks = [
            AudioChunk(
                chunk_id="1",
                text="Test chunk 1",
                audio_path=Path("/tmp/1.mp3"),
                duration_seconds=4.0,
                voice_id="test_voice",
                file_size_bytes=1024,
            ),
            AudioChunk(
                chunk_id="2",
                text="Test chunk 2",
                audio_path=Path("/tmp/2.mp3"),
                duration_seconds=5.0,
                voice_id="test_voice",
                file_size_bytes=2048,
            ),
        ]
        mock_client.generate_audio_chunks = AsyncMock(return_value=mock_audio_chunks)
        
        # Call convenience function
        result = await generate_story_audio(text_chunks, voice_id="test_voice")
        
        # Verify results
        assert len(result) == 2
        assert result[0].text == "Test chunk 1"
        assert result[1].text == "Test chunk 2"
        
        # Verify client was used correctly
        mock_client_class.assert_called_once()
        # The generate_audio_chunks method is called with voice_id as a positional argument
        mock_client.generate_audio_chunks.assert_called_once_with(
            text_chunks, "test_voice"
        )
    
    print("✅ Convenience function test passed")
    return True

async def run_async_tests():
    """Run all async tests."""
    print("\n" + "=" * 60)
    print("Running Async Tests")
    print("=" * 60)
    
    async_tests = [
        ("Text-to-Speech Mock", test_text_to_speech_mock),
        ("Generate Audio Chunks Mock", test_generate_audio_chunks_mock),
        ("Error Handling", test_error_handling),
        ("Convenience Function", test_convenience_function),
    ]
    
    results = []
    for test_name, test_func in async_tests:
        try:
            print(f"\nRunning: {test_name}")
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    return results

async def main():
    """Run all tests."""
    print("ElevenLabs Client Test Suite")
    print("=" * 60)
    
    # Run synchronous tests
    sync_tests = [
        ("AudioChunk Dataclass", test_audio_chunk_dataclass),
        ("Client Initialization", test_client_initialization),
        ("Cache Key Generation", test_cache_key_generation),
        ("Cache Cleanup", test_cache_cleanup),
    ]
    
    sync_results = []
    for test_name, test_func in sync_tests:
        try:
            print(f"\nRunning: {test_name}")
            result = test_func()
            sync_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            sync_results.append((test_name, False))
    
    # Run async tests
    async_results = await run_async_tests()
    
    # Combine results
    results = sync_results + async_results
    
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
        
        # Show configuration status
        print("\n📋 Configuration Status:")
        print(f"   ElevenLabs API configured: {settings.is_elevenlabs_configured()}")
        
        if not settings.is_elevenlabs_configured():
            print("\n⚠️  IMPORTANT: ElevenLabs API is not configured.")
            print("   To use TTS features, please:")
            print("   1. Get an API key from: https://elevenlabs.io/app")
            print("   2. Add it to your .env file:")
            print("      ELEVENLABS_API_KEY=your_api_key_here")
            print("   3. Configure voice IDs (pre-configured in .env.example)")
        
        print("\nElevenLabs Client is ready for use!")
    else:
        print("💥 SOME TESTS FAILED")
        print("\nCheck the errors above and fix them before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)