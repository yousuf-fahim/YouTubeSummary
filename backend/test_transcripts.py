#!/usr/bin/env python3
"""
Test transcript availability for different video types
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.transcript import extract_video_id
from youtube_transcript_api import YouTubeTranscriptApi, _errors

def test_video_transcripts():
    """Test different types of videos for transcript availability"""
    
    test_videos = [
        # Educational content (usually has captions)
        "https://www.youtube.com/watch?v=wJa5Ch0O4BI",  # TED-Ed
        "https://www.youtube.com/watch?v=kuF_Z-6M-_g",  # Kurzgesagt
        "https://www.youtube.com/watch?v=P6FORpg0KVo",  # Veritasium
        
        # Tech reviews (often have auto-captions)
        "https://www.youtube.com/watch?v=_luhn7TLfWU",  # MKBHD
        "https://www.youtube.com/watch?v=8MZ0pLvKxbE",  # LTT
        
        # News/documentaries (usually captioned)
        "https://www.youtube.com/watch?v=l1Ay4XnQLCA",  # BBC
    ]
    
    results = []
    
    for url in test_videos:
        video_id = extract_video_id(url)
        if not video_id:
            results.append({"url": url, "status": "Invalid URL"})
            continue
            
        try:
            # Try to get transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            results.append({
                "url": url,
                "video_id": video_id,
                "status": "✅ Has transcript",
                "entries": len(transcript_list)
            })
        except _errors.TranscriptsDisabled:
            results.append({
                "url": url, 
                "video_id": video_id,
                "status": "❌ Transcripts disabled"
            })
        except _errors.NoTranscriptFound:
            results.append({
                "url": url,
                "video_id": video_id, 
                "status": "❌ No transcript found"
            })
        except Exception as e:
            results.append({
                "url": url,
                "video_id": video_id,
                "status": f"❌ Error: {str(e)[:50]}"
            })
    
    return results

if __name__ == "__main__":
    print("🧪 Testing Video Transcript Availability...")
    print("=" * 60)
    
    results = test_video_transcripts()
    
    working_count = 0
    for result in results:
        print(f"Video ID: {result.get('video_id', 'N/A')}")
        print(f"Status: {result['status']}")
        if 'entries' in result:
            print(f"Transcript entries: {result['entries']}")
            working_count += 1
        print("-" * 40)
    
    print(f"\n📊 Summary: {working_count}/{len(results)} videos have accessible transcripts")
    print("\n💡 Recommendation: Focus on educational channels (TED-Ed, Kurzgesagt, Veritasium)")
    print("   These typically have high-quality captions available.")
