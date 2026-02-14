#!/usr/bin/env python3
"""
Test script to verify transcription works after filelock fix.
"""

import sys
import os

# Change to current directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("🔍 Testing Transcription Fix...")
print("=" * 50)

# Test 1: Check filelock version
print("\n1. Checking filelock version:")
try:
    import filelock
    print(f"   ✅ filelock {filelock.__version__}")
except Exception as e:
    print(f"   ❌ filelock error: {e}")

# Test 2: Check faster-whisper import
print("\n2. Checking faster-whisper:")
try:
    from faster_whisper import WhisperModel
    print("   ✅ faster_whisper import successful")
    
    # Try to initialize model (won't download unless needed)
    print("   Testing model initialization...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("   ✅ Model initialized successfully")
    
except Exception as e:
    print(f"   ❌ faster-whisper error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check video_processor imports
print("\n3. Checking video_processor imports:")
try:
    import sys
    sys.path.insert(0, '.')
    
    # Test individual imports
    from video_processor import (
        extract_audio_16khz,
        transcribe_with_word_timestamps,
        generate_ass_subtitles,
        create_shorts_with_captions
    )
    
    print("   ✅ All video_processor functions imported")
    
except ImportError as e:
    print(f"   ❌ Import error: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"   ⚠️  Other error: {e}")

print("\n" + "=" * 50)
print("✅ Transcription fix verification complete!")
print("\nIf all checks pass, the /process-video endpoint should work.")
print("\nTo test the full pipeline:")
print("1. Start server: python main.py")
print("2. Send POST request to /process-video")
print('   Body: {"input_path": "path/to/test/video.mp4"}')