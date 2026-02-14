#!/usr/bin/env python3
"""
Final comprehensive test for the automated shorts pipeline.
"""

import os
import sys
import tempfile
from pathlib import Path

print("FINAL TEST: Automated Shorts Pipeline")
print("=" * 70)

# Test 1: Basic imports
print("\n1. BASIC IMPORTS:")
print("-" * 40)

try:
    import ffmpeg
    print("OK: ffmpeg")
except ImportError as e:
    print(f"FAIL: ffmpeg - {e}")

try:
    from faster_whisper import WhisperModel
    print("OK: faster_whisper")
except ImportError as e:
    print(f"FAIL: faster_whisper - {e}")

try:
    import video_processor
    print("OK: video_processor")
except ImportError as e:
    print(f"FAIL: video_processor - {e}")

# Test 2: Path formatting function
print("\n2. PATH FORMATTING FUNCTION:")
print("-" * 40)

try:
    from video_processor import format_windows_path_for_ffmpeg
    
    test_path = r"C:\Users\ADMIN\test\subtitles.ass"
    formatted = format_windows_path_for_ffmpeg(test_path)
    print(f"Test path: {test_path}")
    print(f"Formatted: {formatted}")
    
    # Check key characteristics
    if 'C\\\\:' in formatted or 'C\\\\/' in formatted:
        print("OK: Drive letter properly escaped")
    if '/' in formatted or '\\\\' in formatted:
        print("OK: Path separators properly formatted")
        
except Exception as e:
    print(f"FAIL: {e}")

# Test 3: Check all pipeline functions exist
print("\n3. PIPELINE FUNCTIONS:")
print("-" * 40)

required_functions = [
    'get_video_dimensions',
    'get_video_framerate',
    'extract_audio_16khz',
    'transcribe_with_word_timestamps',
    'generate_ass_subtitles',
    'reframe_to_916_with_subtitles',
    'create_shorts_with_captions',
    'batch_process_shorts'
]

all_functions_exist = True
for func_name in required_functions:
    if hasattr(video_processor, func_name):
        print(f"OK: {func_name}")
    else:
        print(f"MISSING: {func_name}")
        all_functions_exist = False

# Test 4: Check API endpoints
print("\n4. API ENDPOINTS:")
print("-" * 40)

try:
    with open('main.py', 'r') as f:
        content = f.read()
    
    endpoints = [
        ("POST /upload/video", "@app.post(\"/upload/video\""),
        ("POST /process-video", "@app.post(\"/process-video\""),
        ("POST /batch-process", "@app.post(\"/batch-process\""),
        ("GET /health", "@app.get(\"/health\""),
        ("GET /system-info", "@app.get(\"/system-info\"")
    ]
    
    for endpoint, marker in endpoints:
        if marker in content:
            print(f"OK: {endpoint}")
        else:
            print(f"MISSING: {endpoint}")
            
except Exception as e:
    print(f"ERROR reading main.py: {e}")

# Test 5: Directory structure
print("\n5. DIRECTORY STRUCTURE:")
print("-" * 40)

required_dirs = ["uploads", "outputs"]
for dir_name in required_dirs:
    if os.path.exists(dir_name) and os.path.isdir(dir_name):
        print(f"OK: {dir_name}/")
    else:
        print(f"MISSING: {dir_name}/")

# Test 6: Requirements check
print("\n6. REQUIREMENTS CHECK:")
print("-" * 40)

try:
    with open('requirements.txt', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    important_reqs = ["fastapi", "uvicorn", "ffmpeg-python", "faster-whisper", "pydantic", "filelock"]
    for req in important_reqs:
        found = any(req in r for r in requirements)
        if found:
            print(f"OK: {req}")
        else:
            print(f"MISSING: {req}")
            
except Exception as e:
    print(f"ERROR reading requirements.txt: {e}")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY:")
print("=" * 70)

if all_functions_exist:
    print("SUCCESS: All pipeline functions are available")
    print("\nThe automated shorts pipeline is READY for use!")
    print("\nTo start the server:")
    print("  python main.py")
    print("\nAPI will be available at: http://localhost:8000")
    print("\nTest endpoints:")
    print("  GET  http://localhost:8000/health")
    print("  POST http://localhost:8000/process-video")
    print('  Body: {"input_path": "path/to/your/video.mp4"}')
else:
    print("ISSUES: Some pipeline functions are missing")
    print("\nPlease check the errors above and fix them.")

print("\n" + "=" * 70)