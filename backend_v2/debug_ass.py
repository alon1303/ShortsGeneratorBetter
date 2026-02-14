#!/usr/bin/env python3
import os
print('Current dir:', os.getcwd())
from video_processor import WordTimestamp, Segment, generate_ass_subtitles

test_segments = [
    Segment(
        text='Hello world this is a test',
        start=0.0,
        end=2.0,
        words=[
            WordTimestamp(word='Hello', start=0.0, end=0.5, confidence=0.9),
            WordTimestamp(word='world', start=0.5, end=1.0, confidence=0.9),
        ]
    )
]

print('Calling generate_ass_subtitles...')
result = generate_ass_subtitles(test_segments, 'debug_subtitles.ass')
print(f'Result: {result}')
print('File exists:', os.path.exists('debug_subtitles.ass'))
if os.path.exists('debug_subtitles.ass'):
    with open('debug_subtitles.ass', 'r', encoding='utf-8') as f:
        content = f.read()
        print('First 500 chars:')
        print(content[:500])
        print('\nChecking for key strings:')
        print('ShortsStyle in content:', 'ShortsStyle' in content)
        print('Alignment=5 in content:', 'Alignment=5' in content)
        print('Outline=5 in content:', 'Outline=5' in content)
        print('Arial Black in content:', 'Arial Black' in content)
        print('Fontsize 80 in content:', ',80,' in content)