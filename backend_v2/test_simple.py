#!/usr/bin/env python3
"""
Simple test for Windows path formatting fix.
"""

import os
import sys

print("Testing Windows Path Formatting for FFmpeg")
print("=" * 60)

# Test the path formatting function
test_paths = [
    r"C:\Users\ADMIN\AppData\Local\Temp\tmp1234\subtitles.ass",
    r"C:\test\video.mp4",
    r"D:\Projects\ShortsGenerator\subtitles.ass",
    r"relative\path\subtitles.ass"
]

print("\nTesting format_windows_path_for_ffmpeg function:")
print("-" * 40)

try:
    from video_processor import format_windows_path_for_ffmpeg
    
    for original_path in test_paths:
        print(f"\nOriginal: {original_path}")
        formatted = format_windows_path_for_ffmpeg(original_path)
        print(f"Formatted: {formatted}")
        
        # Check for common issues
        if '\\' in formatted and not '\\\\' in formatted:
            print("WARNING: Single backslashes may cause issues")
        if ':\\\\' in formatted:
            print("OK: Drive colon properly escaped")
        if formatted.startswith('C\\\\:'):
            print("OK: C: drive properly formatted")
            
except ImportError as e:
    print(f"ERROR importing: {e}")
except Exception as e:
    print(f"ERROR: {e}")

# Test actual import of video_processor
print("\n\nTesting video_processor imports:")
print("-" * 40)

try:
    import video_processor
    print("OK: video_processor module imported")
    
    # Check if key functions exist
    functions_to_check = [
        'format_windows_path_for_ffmpeg',
        'reframe_to_916_with_subtitles',
        'create_shorts_with_captions',
        'transcribe_with_word_timestamps'
    ]
    
    for func_name in functions_to_check:
        if hasattr(video_processor, func_name):
            print(f"OK: {func_name} exists")
        else:
            print(f"WARNING: {func_name} not found")
            
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("\nKey checks:")
print("1. Backslashes -> Forward slashes or double-escaped")
print("2. Drive colon (C:) -> C\\\\:")
print("3. No unescaped backslashes in final string")