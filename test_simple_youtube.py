#!/usr/bin/env python3
"""
Simple test of YouTube Transcript API
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

def simple_test():
    print("Testing simple YouTube Transcript API...")
    
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        # Try the simplest approach
        print(f"Trying to get transcript for {video_id}...")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        print(f"Got transcript with {len(transcript_list)} segments")
        
        # Format the transcript
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript_list)
        
        print(f"✅ Successfully got transcript ({len(transcript_text)} characters)")
        print(f"First 200 characters: {transcript_text[:200]}...")
        
        return transcript_text
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        
        # Try with language specification
        try:
            print("Trying with language codes...")
            for lang in ['en', 'en-US', 'en-GB']:
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    formatter = TextFormatter()
                    transcript_text = formatter.format_transcript(transcript_list)
                    print(f"✅ Got transcript with language {lang} ({len(transcript_text)} characters)")
                    return transcript_text
                except Exception as e2:
                    print(f"Failed with {lang}: {e2}")
                    continue
                    
        except Exception as e3:
            print(f"❌ All language attempts failed: {e3}")
    
    return None

if __name__ == "__main__":
    simple_test()
