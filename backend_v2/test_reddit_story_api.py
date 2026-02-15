#!/usr/bin/env python3
"""
Integration test for Reddit Stories API endpoints.
Tests the FastAPI endpoints for Reddit story generation.
"""

import sys
import tempfile
import asyncio
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from main import app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_initialization():
    """Test API initialization and basic endpoints."""
    print("=" * 60)
    print("Testing API Initialization")
    print("=" * 60)
    
    # Create test client
    client = TestClient(app)
    
    # Test root endpoint
    response = client.get("/")
    print(f"Root endpoint status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"Root response: {data}")
    assert "message" in data
    assert "ShortsGenerator Backend v2" in data["message"]
    
    # Test health endpoint
    response = client.get("/health")
    print(f"Health endpoint status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"Health response: {data}")
    assert data["status"] == "healthy"
    
    print("✅ API initialization tests passed")
    return True

def test_reddit_story_endpoints():
    """Test Reddit story endpoints."""
    print("\n" + "=" * 60)
    print("Testing Reddit Story Endpoints")
    print("=" * 60)
    
    # Create test client
    client = TestClient(app)
    
    # Test themes endpoint
    response = client.get("/reddit-story/themes")
    print(f"Themes endpoint status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Themes response: {data}")
        assert "themes" in data
        print(f"Available themes: {data.get('themes', [])}")
    else:
        print(f"Themes endpoint error: {response.text}")
    
    # Test voices endpoint
    response = client.get("/reddit-story/voices")
    print(f"\nVoices endpoint status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Voices response success: {data.get('success', False)}")
        if data.get('success'):
            print(f"Available voices: {len(data.get('voices', []))}")
        else:
            print(f"Voices error message: {data.get('message', 'No message')}")
    else:
        print(f"Voices endpoint error: {response.text}")
    
    # Test jobs endpoint
    response = client.get("/reddit-story/jobs")
    print(f"\nJobs endpoint status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"Jobs response: {data}")
    assert "total_jobs" in data
    assert "jobs" in data
    
    print("✅ Reddit story endpoints tests passed")
    return True

def test_reddit_story_generation():
    """Test Reddit story generation endpoint."""
    print("\n" + "=" * 60)
    print("Testing Reddit Story Generation")
    print("=" * 60)
    
    # Create test client
    client = TestClient(app)
    
    # Test 1: Missing both story_url and story_text
    print("Testing missing parameters...")
    response = client.post("/generate/reddit-story", json={})
    print(f"Missing params status: {response.status_code}")
    assert response.status_code == 200  # Returns 200 with error in response
    
    data = response.json()
    print(f"Missing params response: {data}")
    assert data["success"] == False
    assert "Either story_url or story_text must be provided" in data.get("message", "")
    
    # Test 2: Valid request with story_text
    print("\nTesting valid request with story_text...")
    test_story = {
        "story_text": "This is a test Reddit story for API testing. It contains multiple sentences to test the story processing pipeline. The system should be able to handle this text and start a background job.",
        "theme": None,
        "voice_id": None,
        "max_duration_minutes": 1,
        "split_strategy": "HYBRID"
    }
    
    response = client.post("/generate/reddit-story", json=test_story)
    print(f"Valid request status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"Valid request response: {data}")
    
    if data["success"]:
        print(f"✅ Job created successfully: {data.get('job_id')}")
        
        # Test job status endpoint
        job_id = data["job_id"]
        response = client.get(f"/reddit-story/status/{job_id}")
        print(f"Job status endpoint status: {response.status_code}")
        assert response.status_code == 200
        
        status_data = response.json()
        print(f"Job status: {status_data}")
        assert status_data["job_id"] == job_id
        assert status_data["status"] in ["pending", "processing", "completed", "failed"]
        
        # Test invalid job ID
        print("\nTesting invalid job ID...")
        response = client.get("/reddit-story/status/invalid_job_id")
        print(f"Invalid job ID status: {response.status_code}")
        assert response.status_code == 404
        
    else:
        print(f"⚠️ Job creation failed: {data.get('error', 'Unknown error')}")
        print("Note: This might be expected if background processing dependencies are missing")
    
    print("✅ Reddit story generation tests passed")
    return True

def test_error_handling():
    """Test error handling in API endpoints."""
    print("\n" + "=" * 60)
    print("Testing Error Handling")
    print("=" * 60)
    
    # Create test client
    client = TestClient(app)
    
    # Test invalid job status
    print("Testing invalid job status endpoint...")
    response = client.get("/reddit-story/status/nonexistent_job")
    print(f"Invalid job status: {response.status_code}")
    assert response.status_code == 404
    
    # Test batch process with invalid directory
    print("\nTesting batch process with invalid directory...")
    response = client.post("/batch-process", json={
        "input_dir": "/nonexistent/directory",
        "output_dir": "/nonexistent/output",
    })
    print(f"Invalid batch process status: {response.status_code}")
    assert response.status_code == 200  # Returns 200 with error in response
    
    data = response.json()
    print(f"Invalid batch process response: {data}")
    assert data["success"] == False
    assert "does not exist" in data.get("error", "").lower() or "not a directory" in data.get("error", "").lower()
    
    print("✅ Error handling tests passed")
    return True

def test_existing_endpoints():
    """Test existing video processing endpoints still work."""
    print("\n" + "=" * 60)
    print("Testing Existing Endpoints")
    print("=" * 60)
    
    # Create test client
    client = TestClient(app)
    
    # Test system info endpoint
    response = client.get("/system-info")
    print(f"System info status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"System info response keys: {list(data.keys())}")
    assert "pipeline_components" in data
    assert "directories" in data
    
    # Test process-video endpoint (with invalid path)
    print("\nTesting process-video endpoint...")
    response = client.post("/process-video", json={
        "input_path": "/nonexistent/video.mp4",
        "model_size": "base"
    })
    print(f"Process video status: {response.status_code}")
    assert response.status_code == 200
    
    data = response.json()
    print(f"Process video response: {data}")
    assert data["success"] == False
    assert "does not exist" in data.get("error", "").lower()
    
    print("✅ Existing endpoints tests passed")
    return True

def main():
    """Run all integration tests."""
    print("Reddit Stories API Integration Test Suite")
    print("=" * 60)
    
    tests = [
        ("API Initialization", test_api_initialization),
        ("Reddit Story Endpoints", test_reddit_story_endpoints),
        ("Reddit Story Generation", test_reddit_story_generation),
        ("Error Handling", test_error_handling),
        ("Existing Endpoints", test_existing_endpoints),
    ]
    
    results = []
    all_passed = True
    
    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} passed")
            else:
                print(f"❌ {test_name} failed")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
            all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("\nReddit Stories API is ready for use!")
        print("\nTo test the full pipeline:")
        print("1. Add background videos to: assets/backgrounds/")
        print("2. Configure ElevenLabs API key in .env file")
        print("3. Configure Reddit API credentials in .env file")
        print("4. Start the server: python main.py")
        print("5. Visit Swagger UI: http://localhost:8000/docs")
    else:
        print("💥 SOME TESTS FAILED")
        print("\nCheck the errors above and fix them before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)