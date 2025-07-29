#!/usr/bin/env python3
"""
Test transcript extraction directly
"""
import asyncio
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

from shared.transcript import get_transcript, _get_transcript_any_language

async def test_transcript():
    print("Testing transcript extraction...")
    
    # Test with Rick Astley video
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"Testing with URL: {video_url}")
    
    try:
        # Test the main function
        transcript = await get_transcript(video_url)
        if transcript:
            print(f"✅ Successfully extracted transcript ({len(transcript)} characters)")
            print(f"First 200 characters: {transcript[:200]}...")
        else:
            print("❌ Failed to extract transcript")
            
            # Test the fallback function directly
            print("Testing YouTube API fallback directly...")
            fallback_transcript = _get_transcript_any_language("dQw4w9WgXcQ")
            if fallback_transcript:
                print(f"✅ Fallback worked ({len(fallback_transcript)} characters)")
                print(f"First 200 characters: {fallback_transcript[:200]}...")
            else:
                print("❌ Fallback also failed")
                
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_transcript())
