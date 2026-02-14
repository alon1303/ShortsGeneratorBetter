#!/usr/bin/env python3
"""
End-to-end API test for the automated shorts pipeline.
Simple version without Unicode characters.
"""

import requests
import time
import os
import sys
from pathlib import Path

def test_health_endpoint(base_url="http://localhost:8000"):
    """Test the health endpoint."""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print(f"OK: Health endpoint - {response.json()}")
            return True
        else:
            print(f"FAIL: Health endpoint - {response.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: Health endpoint - {e}")
        return False

def test_direct_process(base_url="http://localhost:8000", video_path="dummy_test_video.mp4"):
    """Test direct processing without upload."""
    print(f"\nTesting direct process with video: {video_path}")
    
    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"FAIL: Video file not found: {video_path}")
        return False
    
    try:
        # Process the video directly
        print("Processing video directly...")
        process_response = requests.post(
            f"{base_url}/process-video",
            json={"input_path": video_path}
        )
        
        if process_response.status_code == 200:
            process_result = process_response.json()
            print(f"OK: Direct processing successful!")
            print(f"  Success: {process_result.get('success')}")
            print(f"  Output path: {process_result.get('output_path')}")
            print(f"  Segments: {process_result.get('segments_count', 0)}")
            print(f"  Message: {process_result.get('message')}")
            
            # Check if output file was created
            output_path = process_result.get('output_path')
            if output_path and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"OK: Output file created: {output_path} ({file_size} bytes)")
                return True
            else:
                print(f"FAIL: Output file not found: {output_path}")
                return False
        else:
            print(f"FAIL: Direct processing - {process_response.status_code}")
            print(f"  Response: {process_response.text}")
            return False
            
    except Exception as e:
        print(f"ERROR: Direct processing - {e}")
        return False

def test_system_info(base_url="http://localhost:8000"):
    """Test system info endpoint."""
    print("\nTesting system info endpoint...")
    try:
        response = requests.get(f"{base_url}/system-info")
        if response.status_code == 200:
            system_info = response.json()
            print(f"OK: System info retrieved")
            print(f"  Platform: {system_info.get('platform')}")
            print(f"  Python version: {system_info.get('python_version')}")
            print(f"  FFmpeg available: {system_info.get('ffmpeg_available')}")
            print(f"  Whisper model: {system_info.get('whisper_model')}")
            return True
        else:
            print(f"FAIL: System info - {response.status_code}")
            return False
    except Exception as e:
        print(f"ERROR: System info - {e}")
        return False

def main():
    """Run all end-to-end tests."""
    print("=" * 70)
    print("END-TO-END API TEST - Automated Shorts Pipeline")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    video_path = "dummy_test_video.mp4"
    
    # Wait a moment for server to be ready
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    # Run tests
    tests = [
        ("Health endpoint", lambda: test_health_endpoint(base_url)),
        ("System info", lambda: test_system_info(base_url)),
        ("Direct processing", lambda: test_direct_process(base_url, video_path)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Test: {test_name}")
        print(f"{'='*40}")
        result = test_func()
        results.append((test_name, result))
        time.sleep(1)  # Small delay between tests
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n{'='*70}")
    if all_passed:
        print("SUCCESS: ALL TESTS PASSED!")
        print("\nThe automated shorts pipeline is working correctly.")
        print(f"Server: {base_url}")
        print("Endpoints tested:")
        print("  GET  /health")
        print("  GET  /system-info")
        print("  POST /process-video")
    else:
        print("FAILURE: SOME TESTS FAILED")
        print("\nPlease check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())