#!/usr/bin/env python3
"""
Test YouTube API directly to understand the issue
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

from youtube_transcript_api import YouTubeTranscriptApi, _errors
from youtube_transcript_api.formatters import TextFormatter

def test_youtube_api():
    print("Testing YouTube Transcript API directly...")
    
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        # Test 1: Get available transcripts
        print(f"Getting available transcripts for {video_id}...")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        available_transcripts = []
        for transcript in transcript_list:
            available_transcripts.append({
                'language': transcript.language,
                'language_code': transcript.language_code,
                'is_generated': transcript.is_generated,
                'is_translatable': transcript.is_translatable
            })
        
        print(f"Available transcripts: {available_transcripts}")
        
        # Test 2: Try to get the first available transcript
        if available_transcripts:
            first_transcript = next(iter(transcript_list))
            print(f"Trying to get transcript in: {first_transcript.language}")
            
            transcript_data = first_transcript.fetch()
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript_data)
            
            print(f"✅ Successfully got transcript ({len(transcript_text)} characters)")
            print(f"First 200 characters: {transcript_text[:200]}...")
            return transcript_text
        else:
            print("❌ No transcripts available")
            
    except _errors.TranscriptsDisabled:
        print("❌ Transcripts are disabled for this video")
    except _errors.NoTranscriptFound:
        print("❌ No transcript found for this video")
    except _errors.VideoUnavailable:
        print("❌ Video is unavailable")
    except _errors.TooManyRequests:
        print("❌ Too many requests - rate limited")
    except _errors.NotTranslatable:
        print("❌ Transcript is not translatable")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    return None

if __name__ == "__main__":
    test_youtube_api()
