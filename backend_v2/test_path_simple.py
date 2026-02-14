#!/usr/bin/env python3
"""
Simple test for path formatting without Unicode characters.
"""

import os
import sys

print("Testing corrected path formatting function")
print("=" * 60)

try:
    from video_processor import format_windows_path_for_ffmpeg
    
    # Test the exact example from the user
    example = r'C:\Users\ADMIN\Temp\sub.ass'
    expected = r'C\:/Users/ADMIN/Temp/sub.ass'
    result = format_windows_path_for_ffmpeg(example)
    
    print(f"Test 1 - User's example:")
    print(f"  Input:    {example}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    
    if result == expected:
        print("  PASS: Exact match!")
    else:
        print("  FAIL: Does not match")
    
    print()
    
    # Test additional cases
    test_cases = [
        (r'C:\test\video.mp4', r'C\:/test/video.mp4'),
        (r'D:\Projects\ShortsGenerator\subtitles.ass', r'D\:/Projects/ShortsGenerator/subtitles.ass'),
    ]
    
    all_pass = True
    for i, (input_path, expected_path) in enumerate(test_cases, 2):
        result = format_windows_path_for_ffmpeg(input_path)
        
        print(f"Test {i}:")
        print(f"  Input:    {input_path}")
        print(f"  Expected: {expected_path}")
        print(f"  Got:      {result}")
        
        if result == expected_path:
            print("  PASS")
        else:
            print("  FAIL")
            all_pass = False
        
        print()
    
    # Test relative path
    relative_path = r'relative\path\subtitles.ass'
    result = format_windows_path_for_ffmpeg(relative_path)
    print(f"Test relative path:")
    print(f"  Input:    {relative_path}")
    print(f"  Got:      {result}")
    
    # Check it has the right format
    if '\\:' in result and '/' in result:
        print("  PASS: Contains correct formatting")
    else:
        print("  FAIL: Missing correct formatting")
        all_pass = False
    
    print()
    print("=" * 60)
    if all_pass:
        print("SUCCESS: All tests passed!")
    else:
        print("FAILURE: Some tests failed")
        
except ImportError as e:
    print(f"Error importing: {e}")
except Exception as e:
    print(f"Error: {e}")