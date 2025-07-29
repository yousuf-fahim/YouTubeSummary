#!/usr/bin/env python3
"""
Test exactly what the frontend is doing
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

def test_frontend_exact_approach():
    video_id = "dQw4w9WgXcQ"
    
    print("Testing the exact frontend approach step by step...")
    
    # Step 1: Try to import from shared modules (this should fail and trigger the fallback)
    try:
        print("1. Trying to import from shared.transcript...")
        from shared.transcript import extract_video_id, _get_transcript_from_api
        print("   ✅ Successfully imported from shared")
        
        # Use the shared module function
        transcript = _get_transcript_from_api(video_id)
        print(f"   Result: {len(transcript) if transcript else 0} characters")
        return transcript if transcript else "Could not extract transcript from this video"
        
    except ImportError as e:
        print(f"   ❌ ImportError (expected): {e}")
        print("2. Trying fallback approach...")
        
        # Fallback: try youtube-transcript-api directly
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            print("   ✅ Imported YouTubeTranscriptApi")
            
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            print("   ✅ Called get_transcript - this shouldn't work!")
            transcript = ' '.join([t['text'] for t in transcript_list])
            return transcript
            
        except Exception as e:
            print(f"   ❌ Fallback failed: {e}")
            return f"Could not extract transcript: {str(e)}"
            
    except Exception as e:
        print(f"   ❌ Other error: {e}")
        return f"Could not extract transcript: {str(e)}"

if __name__ == "__main__":
    result = test_frontend_exact_approach()
    print(f"\nFinal result: {len(result) if result else 0} characters")
    if result and len(result) > 100:
        print(f"First 100 chars: {result[:100]}")
    else:
        print(f"Result: {result}")
