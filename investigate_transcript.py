#!/usr/bin/env python3
"""
Investigate the FetchedTranscriptSnippet object structure
"""
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

def investigate_transcript_object():
    print("Investigating FetchedTranscriptSnippet object structure...")
    
    video_id = "dQw4w9WgXcQ"
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        
        print(f"Transcript list type: {type(transcript_list)}")
        print(f"Transcript list length: {len(transcript_list)}")
        
        if transcript_list:
            first_item = transcript_list[0]
            print(f"First item type: {type(first_item)}")
            print(f"First item dir: {dir(first_item)}")
            print(f"First item repr: {repr(first_item)}")
            
            # Check if it has text attribute
            if hasattr(first_item, 'text'):
                print(f"First item text: {first_item.text}")
            
            # Check if it has other attributes
            for attr in ['text', 'start', 'duration']:
                if hasattr(first_item, attr):
                    print(f"Attribute {attr}: {getattr(first_item, attr)}")
                    
        return transcript_list
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    investigate_transcript_object()
