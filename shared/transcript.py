import aiohttp
import json
import re
import ssl
import os
from youtube_transcript_api import YouTubeTranscriptApi, _errors
from youtube_transcript_api.formatters import TextFormatter
from .supabase_utils import get_transcript as get_supabase_transcript, save_transcript as save_supabase_transcript

# Create a context that doesn't verify certificates (for development only)
# In production, you should use proper certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def sanitize_filename(title):
    """Convert video title to safe filename"""
    # Remove invalid characters for filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with underscores and limit length
    sanitized = sanitized.replace(' ', '_')
    # Limit length to avoid filesystem issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized

def save_transcript_to_local_file(video_id, transcript, title, channel):
    """Save transcript text to a local file with video title as filename"""
    try:
        # Create safe filename from title
        if title and title != 'Unknown Title':
            safe_title = sanitize_filename(title)
            filename = f"{safe_title}.txt"
        else:
            filename = f"{video_id}.txt"
        
        # Create transcripts directory if it doesn't exist
        transcripts_dir = os.path.join(os.path.dirname(__file__), 'data', 'transcripts')
        os.makedirs(transcripts_dir, exist_ok=True)
        
        filepath = os.path.join(transcripts_dir, filename)
        
        # Write transcript to file with metadata
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Video Title: {title}\n")
            f.write(f"Channel: {channel}\n")
            f.write(f"Video ID: {video_id}\n")
            f.write(f"Extracted: {re.sub(r'\\.[0-9]+', '', str(os.path.getctime(filepath)) if os.path.exists(filepath) else 'Now')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(transcript)
        
        print(f"✅ Transcript saved locally as: {filename}")
        return filepath
    except Exception as e:
        print(f"Error saving transcript to local file: {e}")
        return None

def extract_video_id(url):
    """Extract the video ID from a YouTube URL"""
    youtube_regex = r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

async def get_video_details(video_id):
    """Get video title and channel from YouTube API"""
    try:
        # Try to get the video details from the YouTube API
        # For simplicity we're using a scraping approach here
        # In production, consider using the YouTube Data API
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract title
                    title_match = re.search(r'<meta name="title" content="([^"]+)"', html)
                    title = title_match.group(1) if title_match else "Unknown Title"
                    
                    # Extract channel
                    channel_match = re.search(r'<link itemprop="name" content="([^"]+)"', html)
                    channel = channel_match.group(1) if channel_match else "Unknown Channel"
                    
                    return title, channel
        
        return "Unknown Title", "Unknown Channel"
    except Exception as e:
        print(f"Error getting video details: {e}")
        return "Unknown Title", "Unknown Channel"

async def get_transcript(youtube_url):
    """
    Get the transcript for a YouTube video
    
    Args:
        youtube_url (str): YouTube URL
        
    Returns:
        str: The transcript text or None if not found
    """
    video_id = extract_video_id(youtube_url)
    
    if not video_id:
        print(f"Invalid YouTube URL: {youtube_url}")
        return None
    
    print(f"Extracting transcript for YouTube ID: {video_id}")
    
    # Check if transcript already exists in Supabase
    existing_transcript = get_supabase_transcript(video_id)
    if existing_transcript:
        print(f"Transcript found in Supabase for video ID: {video_id}")
        return existing_transcript.get("transcript_text")
    
    # If transcript doesn't exist in Supabase, extract it and store it
    error_reasons = []
    
    # First try: official YouTube API
    try:
        transcript = _get_transcript_from_api(video_id)
        if transcript:
            print("Successfully retrieved transcript from YouTube API")
            # Get video details (title and channel)
            title, channel = await get_video_details(video_id)
            # Save to Supabase
            save_supabase_transcript(video_id, transcript, title, channel)
            # Save to local file
            save_transcript_to_local_file(video_id, transcript, title, channel)
            return transcript
    except _errors.NoTranscriptFound as e:
        error_reasons.append(f"No transcript available: {str(e)}")
    except _errors.TranscriptsDisabled as e:
        error_reasons.append(f"Transcripts disabled for this video: {str(e)}")
    except _errors.VideoUnavailable as e:
        error_reasons.append(f"Video is unavailable or private: {str(e)}")
    except Exception as e:
        error_reasons.append(f"YouTube API error: {str(e)}")
    
    # Second try: Tactiq
    try:
        transcript = await _get_transcript_from_tactiq(video_id)
        if transcript:
            print("Successfully retrieved transcript from Tactiq")
            # Get video details (title and channel)
            title, channel = await get_video_details(video_id)
            # Save to Supabase
            save_supabase_transcript(video_id, transcript, title, channel)
            # Save to local file
            save_transcript_to_local_file(video_id, transcript, title, channel)
            return transcript
    except Exception as e:
        error_reasons.append(f"Tactiq API error: {str(e)}")
    
    # Third try: YouTube Transcript API with all languages
    try:
        print("Trying to get transcript in any available language...")
        transcript = _get_transcript_any_language(video_id)
        if transcript:
            print("Successfully retrieved transcript in alternative language")
            # Get video details (title and channel)
            title, channel = await get_video_details(video_id)
            # Save to Supabase
            save_supabase_transcript(video_id, transcript, title, channel)
            # Save to local file
            save_transcript_to_local_file(video_id, transcript, title, channel)
            return transcript
    except Exception as e:
        error_reasons.append(f"Failed to get transcript in any language: {str(e)}")
    
    # Log all error reasons for debugging
    print(f"Failed to get transcript for video {video_id}")
    for reason in error_reasons:
        print(f"  - {reason}")
    
    return None

def _get_transcript_any_language(video_id):
    """
    Get transcript in any available language
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: The transcript text or None if not found
    """
    try:
        # Get list of available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # First try manually created transcripts in any language
        for transcript in transcript_list:
            try:
                if not transcript.is_generated:
                    # Get the manually created transcript
                    fetched = transcript.fetch()
                    formatter = TextFormatter()
                    return formatter.format_transcript(fetched)
            except:
                continue
        
        # Then try auto-generated transcripts
        for transcript in transcript_list:
            try:
                if transcript.is_generated:
                    # Get the auto-generated transcript
                    fetched = transcript.fetch()
                    formatter = TextFormatter()
                    return formatter.format_transcript(fetched)
            except:
                continue
                
        # If nothing worked, return None
        return None
        
    except Exception as e:
        print(f"Error getting transcripts in any language: {e}")
        return None

async def _get_transcript_from_tactiq(video_id):
    """
    Get transcript from Tactiq API
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: The transcript text or None if not found
    """
    # Construct the request
    url = f"https://tactiq.io/api/youtube/transcript?videoId={video_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://tactiq.io/tools/youtube-transcript",
        "Accept": "application/json"
    }
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers) as response:
                print(f"Tactiq API returned status code: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    
                    # Format the transcript text from the Tactiq response
                    if isinstance(result, list) and len(result) > 0:
                        transcript_text = ""
                        for segment in result:
                            if "text" in segment:
                                transcript_text += segment["text"] + " "
                        
                        return transcript_text.strip()
                
                return None
    except Exception as e:
        print(f"Error in Tactiq API request: {e}")
        return None

def _get_transcript_from_api(video_id):
    """
    Get transcript using youtube_transcript_api
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: The transcript text or None if not found
    """
    try:
        # Get transcript data using new API
        api = YouTubeTranscriptApi()
        fetched_transcript = api.fetch(video_id, languages=['en', 'en-US'])
        
        # Extract text from snippets
        transcript_parts = []
        for snippet in fetched_transcript.snippets:
            if hasattr(snippet, 'text') and snippet.text:
                text = snippet.text.strip()
                if text:
                    transcript_parts.append(text)
        
        if not transcript_parts:
            raise ValueError("No text found in transcript snippets")
        
        # Join all parts with spaces
        full_transcript = ' '.join(transcript_parts)
        
        if len(full_transcript.strip()) > 0:
            return full_transcript
        else:
            raise ValueError("Empty transcript after processing")
            
    except Exception as e:
        print(f"YouTube API transcript error: {e}")
        raise