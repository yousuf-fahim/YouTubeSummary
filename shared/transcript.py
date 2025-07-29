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
            # Fix f-string with backslash issue
            timestamp = str(os.path.getctime(filepath)) if os.path.exists(filepath) else 'Now'
            cleaned_timestamp = re.sub(r'\.[0-9]+', '', timestamp)
            f.write(f"Extracted: {cleaned_timestamp}\n")
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
    try:
        existing_transcript = get_supabase_transcript(video_id)
        if existing_transcript:
            print(f"Transcript found in Supabase for video ID: {video_id}")
            return existing_transcript.get("transcript_text")
    except Exception as e:
        print(f"Error checking Supabase transcript: {e}")
        # Continue without Supabase - we can still get transcripts
    
    # First try: Tactiq (works best with cloud IPs)
    try:
        print("Trying Tactiq API...")
        transcript = await _get_transcript_from_tactiq(video_id)
        if transcript and len(transcript.strip()) > 50:  # Make sure we got substantial content
            print("Successfully retrieved transcript from Tactiq")
            # Get video details (title and channel)
            title, channel = await get_video_details(video_id)
            # Try to save to Supabase (but don't fail if it doesn't work)
            try:
                save_supabase_transcript(video_id, transcript, title, channel)
            except Exception as e:
                print(f"Warning: Could not save to Supabase: {e}")
            # Save to local file
            save_transcript_to_local_file(video_id, transcript, title, channel)
            return transcript
        else:
            print("Tactiq returned empty or short transcript")
    except Exception as e:
        print(f"Tactiq API error: {e}")
    
    # Second try: YouTube Transcript API (fallback)
    try:
        print("Trying YouTube Transcript API...")
        transcript = _get_transcript_any_language(video_id)
        if transcript and len(transcript.strip()) > 50:
            print("Successfully retrieved transcript from YouTube API")
            # Get video details (title and channel)
            title, channel = await get_video_details(video_id)
            # Try to save to Supabase (but don't fail if it doesn't work)
            try:
                save_supabase_transcript(video_id, transcript, title, channel)
            except Exception as e:
                print(f"Warning: Could not save to Supabase: {e}")
            # Save to local file
            save_transcript_to_local_file(video_id, transcript, title, channel)
            return transcript
    except Exception as e:
        print(f"YouTube API error: {e}")
    
    print(f"Failed to get transcript for video {video_id}")
    return None

def _get_transcript_any_language(video_id):
    """
    Simple fallback using YouTube Transcript API
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: The transcript text or None if not found
    """
    try:
        # Use instance method (correct for this API version)
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        formatter = TextFormatter()
        result = formatter.format_transcript(transcript_list)
        if result and len(result.strip()) > 20:
            print(f"YouTube API returned {len(result)} characters")
            return result
    except Exception as e:
        print(f"YouTube Transcript API failed: {e}")
        try:
            # Try with common language codes as fallback
            for lang in ['en', 'en-US', 'en-GB']:
                try:
                    api = YouTubeTranscriptApi()
                    transcript_list = api.fetch(video_id, languages=[lang])
                    formatter = TextFormatter()
                    result = formatter.format_transcript(transcript_list)
                    if result and len(result.strip()) > 20:
                        print(f"YouTube API with {lang} returned {len(result)} characters")
                        return result
                except Exception as e2:
                    print(f"YouTube API with {lang} failed: {e2}")
                    continue
        except Exception as e3:
            print(f"All YouTube API attempts failed: {e3}")
    
    return None

async def _get_transcript_from_tactiq(video_id):
    """
    Get transcript from Tactiq API (alternative approach)
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: The transcript text or None if not found
    """
    try:
        # Let's try a different approach - use the Tactiq web scraping method
        # Since the direct API endpoint was returning 404, let's skip Tactiq for now
        # and rely on the YouTube API which we know works
        print("Skipping Tactiq API - using YouTube API instead")
        return None
        
    except Exception as e:
        print(f"Error in Tactiq API request: {e}")
        return None

def _get_transcript_from_api(video_id):
    """
    Simple fallback using YouTube Transcript API directly
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.fetch(video_id)
        formatter = TextFormatter()
        return formatter.format_transcript(transcript_list)
    except Exception as e:
        print(f"YouTube API transcript error: {e}")
        raise