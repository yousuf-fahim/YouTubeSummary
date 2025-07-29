#!/usr/bin/env python3
"""
Test the correct YouTube Transcript API usage
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
    print("✅ Successfully imported YouTube Transcript API")
except ImportError as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)

def test_correct_usage():
    print("Testing correct YouTube Transcript API usage...")
    
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        # Check what methods are actually available
        print(f"Available methods: {[method for method in dir(YouTubeTranscriptApi) if not method.startswith('_')]}")
        
        # Try different approaches based on the API version
        transcript_text = None
        
        # Method 1: Direct call (newer versions)
        try:
            print("Trying direct get_transcript call...")
            if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            else:
                # Method 2: Instance method (older versions)
                print("Using instance method...")
                api = YouTubeTranscriptApi()
                if hasattr(api, 'get_transcript'):
                    transcript_list = api.get_transcript(video_id)
                elif hasattr(api, 'fetch'):
                    transcript_list = api.fetch(video_id)
                else:
                    print("❌ No suitable method found")
                    return None
            
            if transcript_list:
                print(f"Got transcript with {len(transcript_list)} segments")
                
                # Format the transcript
                formatter = TextFormatter()
                transcript_text = formatter.format_transcript(transcript_list)
                
                print(f"✅ Successfully got transcript ({len(transcript_text)} characters)")
                print(f"First 200 characters: {transcript_text[:200]}...")
                
                return transcript_text
                
        except Exception as e:
            print(f"❌ Error getting transcript: {e}")
            print(f"Error type: {type(e)}")
            
            # Try alternative approach
            try:
                print("Trying alternative approach with language codes...")
                for lang in ['en', 'en-US', 'auto']:
                    try:
                        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                        else:
                            api = YouTubeTranscriptApi()
                            transcript_list = api.get_transcript(video_id, languages=[lang])
                            
                        formatter = TextFormatter()
                        transcript_text = formatter.format_transcript(transcript_list)
                        print(f"✅ Got transcript with language {lang} ({len(transcript_text)} characters)")
                        return transcript_text
                        
                    except Exception as e2:
                        print(f"Failed with {lang}: {e2}")
                        continue
                        
            except Exception as e3:
                print(f"❌ All attempts failed: {e3}")
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    return None

if __name__ == "__main__":
    test_correct_usage()
