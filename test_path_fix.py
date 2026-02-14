#!/usr/bin/env python3
"""
Test the corrected path formatting function.
"""

import os
import sys

print("Testing corrected path formatting function")
print("=" * 60)

# Test the function
test_cases = [
    (r'C:\Users\ADMIN\Temp\sub.ass', r'C\:/Users/ADMIN/Temp/sub.ass'),
    (r'C:\test\video.mp4', r'C\:/test/video.mp4'),
    (r'D:\Projects\ShortsGenerator\subtitles.ass', r'D\:/Projects/ShortsGenerator/subtitles.ass'),
    (r'relative\path\subtitles.ass', None),  # Will be converted to absolute path
]

try:
    from video_processor import format_windows_path_for_ffmpeg
    
    all_passed = True
    for input_path, expected in test_cases:
        result = format_windows_path_for_ffmpeg(input_path)
        
        if expected is not None:
            # For paths with expected output
            if result == expected:
                print(f"✓ PASS: {input_path}")
                print(f"  -> {result}")
            else:
                print(f"✗ FAIL: {input_path}")
                print(f"  Expected: {expected}")
                print(f"  Got:      {result}")
                all_passed = False
        else:
            # For relative paths, just show the result
            print(f"✓ Test: {input_path}")
            print(f"  -> {result}")
            
            # Check it contains the correct formatting
            if '\\:' in result and '/' in result:
                print(f"  ✓ Contains correct formatting")
            else:
                print(f"  ✗ Missing correct formatting")
                all_passed = False
        
        print()
    
    # Test the exact example from the user
    print("Testing user's exact example:")
    print("-" * 40)
    example = r'C:\Users\ADMIN\Temp\sub.ass'
    expected = r'C\:/Users/ADMIN/Temp/sub.ass'
    result = format_windows_path_for_ffmpeg(example)
    
    print(f"Input:    {example}")
    print(f"Expected: {expected}")
    print(f"Got:      {result}")
    
    if result == expected:
        print("✓ Exact match!")
    else:
        print("✗ Does not match")
        all_passed = False
    
    print()
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
        
except ImportError as e:
    print(f"Error importing: {e}")
except Exception as e:
    print(f"Error: {e}")