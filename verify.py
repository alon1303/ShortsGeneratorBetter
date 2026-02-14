#!/usr/bin/env python3
"""
Simple verification script for the shorts pipeline.
"""

import os
import sys

# Change to current directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("🔍 Verifying Automated Shorts Pipeline Installation...")
print("=" * 50)

# Test 1: Check Python version
print("\n1. Python Version:")
print(f"   Python {sys.version}")

# Test 2: Check if we can import modules
print("\n2. Module Imports:")
modules_to_test = [
    ("ffmpeg", "ffmpeg"),
    ("faster_whisper", "WhisperModel"),
    ("video_processor", "create_shorts_with_captions"),
]

all_imports_ok = True
for module_name, import_name in modules_to_test:
    try:
        if module_name == import_name:
            __import__(module_name)
            print(f"   ✅ {module_name}")
        else:
            exec(f"from {module_name} import {import_name}")
            print(f"   ✅ {module_name}.{import_name}")
    except ImportError as e:
        print(f"   ❌ {module_name}: {e}")
        all_imports_ok = False
    except Exception as e:
        print(f"   ⚠️  {module_name}: {e}")

# Test 3: Check directory structure
print("\n3. Directory Structure:")
required_dirs = ["uploads", "outputs"]
for dir_name in required_dirs:
    if os.path.exists(dir_name) and os.path.isdir(dir_name):
        print(f"   ✅ {dir_name}/")
    else:
        print(f"   ❌ {dir_name}/ (missing)")

# Test 4: Check main API file
print("\n4. API Endpoints:")
try:
    with open('main.py', 'r') as f:
        content = f.read()
    
    endpoints = [
        ("POST /upload/video", "@app.post(\"/upload/video\""),
        ("POST /process-video", "@app.post(\"/process-video\""),
        ("POST /batch-process", "@app.post(\"/batch-process\""),
        ("GET /health", "@app.get(\"/health\""),
    ]
    
    for endpoint, marker in endpoints:
        if marker in content:
            print(f"   ✅ {endpoint}")
        else:
            print(f"   ❌ {endpoint}")
except Exception as e:
    print(f"   ❌ Error reading main.py: {e}")

# Test 5: Check requirements
print("\n5. Requirements Check:")
try:
    with open('requirements.txt', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    important_reqs = ["fastapi", "uvicorn", "ffmpeg-python", "faster-whisper", "pydantic"]
    for req in important_reqs:
        found = any(req in r for r in requirements)
        if found:
            print(f"   ✅ {req}")
        else:
            print(f"   ❌ {req} (missing from requirements.txt)")
except Exception as e:
    print(f"   ❌ Error reading requirements.txt: {e}")

print("\n" + "=" * 50)
if all_imports_ok:
    print("✅ Verification Complete: Pipeline is ready!")
    print("\nTo start the server:")
    print("  python main.py")
    print("\nAPI will be available at: http://localhost:8000")
    print("\nTest endpoints:")
    print("  GET  http://localhost:8000/health")
    print("  POST http://localhost:8000/process-video")
    print('  Body: {"input_path": "path/to/your/video.mp4"}')
else:
    print("⚠️  Some issues found. Please install missing modules:")
    print("  pip install -r requirements.txt")
    
print("\n" + "=" * 50)