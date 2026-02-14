#!/usr/bin/env python3
"""
Test script for the automated shorts pipeline.
"""

import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_module_imports():
    """Test that all required modules can be imported."""
    print("Testing module imports...")
    
    modules_to_test = [
        ("video_processor", "create_shorts_with_captions"),
        ("ffmpeg", None),
        ("faster_whisper", "WhisperModel"),
    ]
    
    all_passed = True
    
    for module_name, attribute_name in modules_to_test:
        try:
            if attribute_name:
                exec(f"from {module_name} import {attribute_name}")
                print(f"  ✅ {module_name}.{attribute_name}")
            else:
                exec(f"import {module_name}")
                print(f"  ✅ {module_name}")
        except ImportError as e:
            print(f"  ❌ {module_name}: {e}")
            all_passed = False
        except Exception as e:
            print(f"  ⚠️  {module_name}: {e}")
    
    return all_passed

def test_pipeline_structure():
    """Test the pipeline function structure."""
    print("\nTesting pipeline structure...")
    
    try:
        from video_processor import (
            get_video_dimensions,
            get_video_framerate,
            extract_audio_16khz,
            transcribe_with_word_timestamps,
            generate_ass_subtitles,
            reframe_to_916_with_subtitles,
            create_shorts_with_captions
        )
        
        functions = [
            "get_video_dimensions",
            "get_video_framerate", 
            "extract_audio_16khz",
            "transcribe_with_word_timestamps",
            "generate_ass_subtitles",
            "reframe_to_916_with_subtitles",
            "create_shorts_with_captions"
        ]
        
        for func in functions:
            print(f"  ✅ {func}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Failed to import functions: {e}")
        return False

def test_api_structure():
    """Test that the API endpoints are properly defined."""
    print("\nTesting API structure...")
    
    try:
        # Read main.py to check for endpoints
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        endpoints = [
            ("POST /upload/video", "@app.post(\"/upload/video\""),
            ("POST /process-video", "@app.post(\"/process-video\""),
            ("POST /batch-process", "@app.post(\"/batch-process\""),
            ("GET /health", "@app.get(\"/health\""),
            ("GET /system-info", "@app.get(\"/system-info\"")
        ]
        
        all_found = True
        for endpoint_name, search_string in endpoints:
            if search_string in content:
                print(f"  ✅ {endpoint_name}")
            else:
                print(f"  ❌ {endpoint_name} not found")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"  ❌ Error reading API structure: {e}")
        return False

def test_directory_structure():
    """Test that required directories exist."""
    print("\nTesting directory structure...")
    
    required_dirs = [
        "uploads",
        "outputs"
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ❌ {dir_name}/ (missing)")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests."""
    print("=" * 60)
    print("Automated Shorts Pipeline - System Test")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_module_imports),
        ("Pipeline Structure", test_pipeline_structure),
        ("API Structure", test_api_structure),
        ("Directory Structure", test_directory_structure),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test failed with error: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! The pipeline is ready.")
        print("\nNext steps:")
        print("1. Start the FastAPI server: python main.py")
        print("2. Use the /process-video endpoint with a video file")
        print("3. Check the outputs/ directory for processed shorts")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())