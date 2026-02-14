#!/usr/bin/env python3
"""
End-to-end API test for the automated shorts pipeline.
Tests the complete workflow: upload video -> process -> get result.
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
            print(f"✓ Health endpoint OK: {response.json()}")
            return True
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health endpoint error: {e}")
        return False

def test_upload_and_process(base_url="http://localhost:8000", video_path="dummy_test_video.mp4"):
    """Test uploading a video and processing it through the pipeline."""
    print(f"\nTesting upload and process with video: {video_path}")
    
    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
        return False
    
    # Upload the video
    print("Uploading video...")
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (os.path.basename(video_path), f, 'video/mp4')}
            response = requests.post(f"{base_url}/upload/video", files=files)
        
        if response.status_code == 200:
            upload_result = response.json()
            print(f"✓ Video uploaded successfully")
            print(f"  Upload ID: {upload_result.get('upload_id')}")
            print(f"  File path: {upload_result.get('file_path')}")
            
            # Now process the uploaded video
            print("\nProcessing video through pipeline...")
            process_response = requests.post(
                f"{base_url}/process-video",
                json={"input_path": upload_result.get('file_path')}
            )
            
            if process_response.status_code == 200:
                process_result = process_response.json()
                print(f"✓ Video processed successfully!")
                print(f"  Success: {process_result.get('success')}")
                print(f"  Output path: {process_result.get('output_path')}")
                print(f"  Segments: {process_result.get('segments_count', 0)}")
                print(f"  Message: {process_result.get('message')}")
                
                # Check if output file was created
                output_path = process_result.get('output_path')
                if output_path and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"✓ Output file created: {output_path} ({file_size} bytes)")
                    return True
                else:
                    print(f"✗ Output file not found: {output_path}")
                    return False
            else:
                print(f"✗ Processing failed: {process_response.status_code}")
                print(f"  Response: {process_response.text}")
                return False
        else:
            print(f"✗ Upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error during upload/process: {e}")
        return False

def test_direct_process(base_url="http://localhost:8000", video_path="dummy_test_video.mp4"):
    """Test direct processing without upload."""
    print(f"\nTesting direct process with video: {video_path}")
    
    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
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
            print(f"✓ Direct processing successful!")
            print(f"  Success: {process_result.get('success')}")
            print(f"  Output path: {process_result.get('output_path')}")
            print(f"  Segments: {process_result.get('segments_count', 0)}")
            print(f"  Message: {process_result.get('message')}")
            
            # Check if output file was created
            output_path = process_result.get('output_path')
            if output_path and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"✓ Output file created: {output_path} ({file_size} bytes)")
                return True
            else:
                print(f"✗ Output file not found: {output_path}")
                return False
        else:
            print(f"✗ Direct processing failed: {process_response.status_code}")
            print(f"  Response: {process_response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error during direct processing: {e}")
        return False

def test_system_info(base_url="http://localhost:8000"):
    """Test system info endpoint."""
    print("\nTesting system info endpoint...")
    try:
        response = requests.get(f"{base_url}/system-info")
        if response.status_code == 200:
            system_info = response.json()
            print(f"✓ System info retrieved:")
            print(f"  Platform: {system_info.get('platform')}")
            print(f"  Python version: {system_info.get('python_version')}")
            print(f"  FFmpeg available: {system_info.get('ffmpeg_available')}")
            print(f"  Whisper model: {system_info.get('whisper_model')}")
            return True
        else:
            print(f"✗ System info failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ System info error: {e}")
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
        ("Upload and process", lambda: test_upload_and_process(base_url, video_path)),
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
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n{'='*70}")
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\nThe automated shorts pipeline is working correctly.")
        print(f"Server: {base_url}")
        print("Endpoints tested:")
        print("  GET  /health")
        print("  GET  /system-info")
        print("  POST /upload/video")
        print("  POST /process-video")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())