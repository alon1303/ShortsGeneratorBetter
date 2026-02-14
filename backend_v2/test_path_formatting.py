#!/usr/bin/env python3
"""
Test script to verify Windows path formatting for FFmpeg.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 Testing Windows Path Formatting for FFmpeg")
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
            print("⚠️  Warning: Single backslashes may cause issues")
        if ':\\\\' in formatted:
            print("✅ Drive colon properly escaped")
        if formatted.startswith('C\\\\:'):
            print("✅ C: drive properly formatted")
            
except ImportError as e:
    print(f"❌ Error importing: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test actual FFmpeg command construction
print("\n\nTesting FFmpeg command construction:")
print("-" * 40)

try:
    import ffmpeg
    
    # Create a test subtitle path
    test_sub_path = r"C:\Users\ADMIN\AppData\Local\Temp\test_subtitles.ass"
    formatted_path = format_windows_path_for_ffmpeg(test_sub_path)
    
    print(f"Test subtitle path: {test_sub_path}")
    print(f"Formatted for FFmpeg: {formatted_path}")
    
    # Try to build an FFmpeg command (won't execute)
    print("\nBuilding FFmpeg command structure...")
    try:
        cmd = (
            ffmpeg
            .input('test_input.mp4')
            .filter('subtitles', formatted_path)
            .output('test_output.mp4')
        )
        print("✅ FFmpeg command built successfully")
        print(f"Command would use: subtitles={formatted_path}")
    except Exception as e:
        print(f"❌ Error building FFmpeg command: {e}")
        
except ImportError as e:
    print(f"❌ FFmpeg not available: {e}")

print("\n" + "=" * 60)
print("✅ Path formatting test complete!")
print("\nKey checks:")
print("1. Backslashes → Forward slashes or double-escaped")
print("2. Drive colon (C:) → C\\\\:")
print("3. No unescaped backslashes in final string")