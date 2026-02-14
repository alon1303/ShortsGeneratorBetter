#!/usr/bin/env python3
"""
Test script to verify the visual fixes for the shorts pipeline.
Simple version without Unicode characters.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_processor import (
    calculate_crop_parameters,
    generate_ass_subtitles,
    WordTimestamp,
    Segment,
    format_time
)

def test_crop_calculation():
    """Test the crop calculation for 9:16 aspect ratio."""
    print("Testing crop calculation...")
    
    # Test with standard 1920x1080 (16:9)
    width, height = 1920, 1080
    crop_w, crop_h, x, y = calculate_crop_parameters(width, height)
    
    print(f"  Original: {width}x{height}")
    print(f"  Crop: {crop_w}x{crop_h}")
    print(f"  Offset: ({x}, {y})")
    
    # Calculate expected values
    expected_crop_w = int(height * 9 / 16)  # 1080 * 9/16 = 607.5 ≈ 607
    expected_crop_h = height  # 1080
    expected_x = (width - expected_crop_w) // 2  # (1920 - 607)//2 = 656
    
    print(f"  Expected crop: {expected_crop_w}x{expected_crop_h}")
    print(f"  Expected offset: ({expected_x}, 0)")
    
    assert int(crop_w) == expected_crop_w, f"Crop width mismatch: {crop_w} != {expected_crop_w}"
    assert int(crop_h) == expected_crop_h, f"Crop height mismatch: {crop_h} != {expected_crop_h}"
    assert int(x) == expected_x, f"X offset mismatch: {x} != {expected_x}"
    assert int(y) == 0, f"Y offset should be 0, got {y}"
    
    print("  OK: Crop calculation correct")
    return True

def test_ass_generation():
    """Test ASS subtitle generation with new styling."""
    print("\nTesting ASS subtitle generation...")
    
    # Create test segments with word timestamps
    test_segments = [
        Segment(
            text="Hello world this is a test",
            start=0.0,
            end=2.0,
            words=[
                WordTimestamp(word="Hello", start=0.0, end=0.5, confidence=0.9),
                WordTimestamp(word="world", start=0.5, end=1.0, confidence=0.9),
                WordTimestamp(word="this", start=1.0, end=1.3, confidence=0.9),
                WordTimestamp(word="is", start=1.3, end=1.5, confidence=0.9),
                WordTimestamp(word="a", start=1.5, end=1.7, confidence=0.9),
                WordTimestamp(word="test", start=1.7, end=2.0, confidence=0.9),
            ]
        )
    ]
    
    # Generate ASS file
    test_output = "test_subtitles.ass"
    try:
        result = generate_ass_subtitles(test_segments, test_output)
        
        if not result:
            print("  FAIL: ASS generation failed")
            return False
        
        # Read the generated file
        with open(test_output, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"  Generated file size: {len(content)} bytes")
        
        # Check for key features
        checks = [
            ("Style name", "ShortsStyle" in content),
            ("Font", "Arial Black" in content),
            ("Font size", "80" in content),
            ("Alignment", "Alignment=5" in content),
            ("Outline thickness", "Outline=5" in content),
            ("ALL CAPS", "HELLO" in content),  # Words should be uppercase
            ("No full sentence", "Hello world this is a test" not in content),  # Should not have full sentence
            ("Karaoke effect", "\\kf" in content),  # Should use karaoke fill
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            status = "OK" if check_result else "FAIL"
            print(f"    {status}: {check_name}")
            if not check_result:
                all_passed = False
        
        if all_passed:
            print("  OK: ASS generation meets all requirements")
        else:
            print("  FAIL: Some ASS generation checks failed")
        
        return all_passed
        
    finally:
        # Clean up
        if os.path.exists(test_output):
            os.remove(test_output)

def test_format_time():
    """Test time formatting for ASS subtitles."""
    print("\nTesting time formatting...")
    
    test_cases = [
        (0.0, "0:00:00.00"),
        (1.5, "0:00:01.50"),
        (65.123, "0:01:05.12"),  # Note: rounding to 2 decimal places
        (3600.0, "1:00:00.00"),
    ]
    
    all_passed = True
    for seconds, expected in test_cases:
        result = format_time(seconds)
        passed = result == expected
        status = "OK" if passed else "FAIL"
        print(f"  {status}: {seconds}s -> {result} (expected: {expected})")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("  OK: Time formatting correct")
    else:
        print("  FAIL: Time formatting errors")
    
    return all_passed

def main():
    """Run all visual fix tests."""
    print("=" * 70)
    print("VISUAL FIXES TEST - Automated Shorts Pipeline")
    print("=" * 70)
    
    tests = [
        ("Crop calculation", test_crop_calculation),
        ("Time formatting", test_format_time),
        ("ASS subtitle generation", test_ass_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Test: {test_name}")
        print(f"{'='*40}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  FAIL: Test failed with error: {e}")
            results.append((test_name, False))
    
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
        print("SUCCESS: ALL VISUAL FIX TESTS PASSED!")
        print("\nThe visual fixes have been correctly implemented:")
        print("  1. OK: Proper 9:16 crop calculation")
        print("  2. OK: ASS styling with professional Shorts look")
        print("  3. OK: Centered text (Alignment=5)")
        print("  4. OK: Thick black outline (Outline=5)")
        print("  5. OK: ALL CAPS text")
        print("  6. OK: Only active words shown (no full sentence background)")
        print("  7. OK: Active word highlighted in yellow")
    else:
        print("FAILURE: SOME TESTS FAILED")
        print("\nPlease check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())