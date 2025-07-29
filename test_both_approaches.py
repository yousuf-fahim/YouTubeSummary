#!/usr/bin/env python3
"""
Test both YouTube API approaches to see which one works
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

print("Testing YouTube Transcript API approaches...")

video_id = "dQw4w9WgXcQ"

# Test 1: Direct approach (what frontend fallback uses)
print("\n1. Testing direct approach (frontend fallback):")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    transcript = ' '.join([t['text'] for t in transcript_list])
    print(f"✅ Direct approach worked: {len(transcript)} characters")
    print(f"First 100 chars: {transcript[:100]}")
except Exception as e:
    print(f"❌ Direct approach failed: {e}")

# Test 2: Instance approach (what we're currently using)
print("\n2. Testing instance approach (current shared implementation):")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
    api = YouTubeTranscriptApi()
    transcript_list = api.fetch(video_id)
    formatter = TextFormatter()
    transcript = formatter.format_transcript(transcript_list)
    print(f"✅ Instance approach worked: {len(transcript)} characters")
    print(f"First 100 chars: {transcript[:100]}")
except Exception as e:
    print(f"❌ Instance approach failed: {e}")

# Test 3: Check if get_transcript is available as static method
print("\n3. Checking available static methods:")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    static_methods = [method for method in dir(YouTubeTranscriptApi) if not method.startswith('_') and callable(getattr(YouTubeTranscriptApi, method))]
    print(f"Available static methods: {static_methods}")
    
    # Try to call get_transcript directly
    if hasattr(YouTubeTranscriptApi, 'get_transcript'):
        print("✅ get_transcript is available as static method")
    else:
        print("❌ get_transcript is NOT available as static method")
        
except Exception as e:
    print(f"❌ Error checking methods: {e}")
