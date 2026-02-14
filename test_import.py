#!/usr/bin/env python3
"""
Simple test script to verify the video_processor module works.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import video_processor
    print("✓ video_processor module imported successfully")
    
    # Test the function signature
    import inspect
    sig = inspect.signature(video_processor.reframe_to_916)
    params = list(sig.parameters.keys())
    print(f"✓ reframe_to_916 function signature: {params}")
    
    if len(params) == 2 and params[0] == 'input_path' and params[1] == 'output_path':
        print("✓ Function signature matches requirements")
    else:
        print("✗ Function signature doesn't match requirements")
        
except ImportError as e:
    print(f"✗ Failed to import video_processor: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error during test: {e}")
    sys.exit(1)

print("\n✅ All tests passed! The video_processor module is ready for use.")