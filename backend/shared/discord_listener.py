import os
import json
import time
import asyncio
import re
from datetime import datetime

from .transcript import get_transcript, extract_video_id
from .summarize import chunk_and_summarize
from .discord_utils import send_discord_message, send_file_to_discord

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

def is_valid_youtube_url(url):
    """
    Check if a URL is a valid YouTube URL
    
    Args:
        url (str): URL to check
        
    Returns:
        bool: True if valid YouTube URL, False otherwise
    """
    # Check for empty input
    if not url:
        return False
    
    # Check for common YouTube URL patterns
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.match(youtube_regex, url)
    
    return bool(match)

def is_youtube_short(url):
    """
    Check if a URL is a YouTube Short
    
    Args:
        url (str): URL to check
        
    Returns:
        bool: True if YouTube Short, False otherwise
    """
    # Check for '/shorts/' in the URL
    shorts_pattern = r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
    return bool(re.match(shorts_pattern, url))

def is_youtube_live(video_id):
    """
    Check if a video is a YouTube Live stream
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        bool: True if live stream, False otherwise or if check fails
    """
    try:
        # Use YouTubeAPI module to check if video is live
        import requests
        from urllib.parse import urlencode
        
        # Try to get video info from YouTube's oembed endpoint
        oembed_url = f"https://www.youtube.com/oembed?{urlencode({'url': f'https://www.youtube.com/watch?v={video_id}', 'format': 'json'})}"
        response = requests.get(oembed_url, timeout=3)
        
        if response.status_code == 200:
            # Check if title contains "live" or other indicators
            data = response.json()
            title = data.get('title', '').lower()
            author = data.get('author_name', '').lower()
            
            # Look for common live stream indicators
            live_indicators = ['🔴', 'live', 'stream', 'streaming']
            return any(indicator in title.lower() for indicator in live_indicators)
        
        return False
    except Exception as e:
        print(f"Error checking if video is live: {e}")
        return False

class DiscordListener:
    def __init__(self):
        self.processed_videos = self._load_processed_videos()
        self.last_check_time = time.time()
        
        print(f"Discord listener initialized with {len(self.processed_videos)} processed videos")
    
    def _load_processed_videos(self):
        """Load list of already processed video IDs from Supabase"""
        try:
            from .supabase_utils import get_all_summaries
            summaries = get_all_summaries()
            if summaries:
                return {summary.get("video_id") for summary in summaries if summary.get("video_id")}
            return set()
        except Exception as e:
            print(f"Error loading processed videos from Supabase: {e}")
            return set()
    
    def _save_processed_video(self, video_id, summary, url):
        """Mark video as processed (summary is saved to Supabase elsewhere)"""
        # Add to in-memory set to avoid reprocessing during this session
        self.processed_videos.add(video_id)
    
    def _extract_youtube_url_from_notifyme(self, message_content):
        """Extract YouTube URL from a NotifyMe bot message"""
        # Extract short format URLs (youtu.be/ID)
        short_url_pattern = r'youtu\.be/([a-zA-Z0-9_-]+)'
        short_match = re.search(short_url_pattern, message_content)
        if short_match:
            video_id = short_match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Extract long format URLs (youtube.com/watch?v=ID)
        long_url_pattern = r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)'
        long_match = re.search(long_url_pattern, message_content)
        if long_match:
            return long_match.group(0)
        
        return None
    
    def _parse_notifyme_message(self, message_content):
        """Parse a NotifyMe bot message to extract video information"""
        # Extract video URL
        url = self._extract_youtube_url_from_notifyme(message_content)
        if not url:
            return None
        
        # Try to extract channel name (pattern: "Channel Name just posted a new video!")
        channel_pattern = r'(.+?) just posted a new video!'
        channel_match = re.search(channel_pattern, message_content)
        channel_name = channel_match.group(1) if channel_match else "Unknown Channel"
        
        # Try to extract video title (often appears as a link)
        title_pattern = r'Build A One-Person Business As A Beginner|[^\n]+(?=\n*https?://)'
        title_match = re.search(title_pattern, message_content)
        title = title_match.group(0) if title_match else "Unknown Title"
        
        return {
            "url": url,
            "channel_name": channel_name,
            "title": title,
            "video_id": extract_video_id(url)
        }
        
    async def process_message(self, message, force=False):
        """
        Process a YouTube video URL or message containing a YouTube URL
        
        Args:
            message (str): YouTube URL or message containing a YouTube URL
            force (bool): Whether to force processing even if the video was processed before
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        print(f"Processing message: {message}")
        
        # First check if this is a direct YouTube URL
        if is_valid_youtube_url(message):
            url = message
            print(f"Detected direct YouTube URL: {url}")
        else:
            # Try to extract YouTube URL from message (could be a NotifyMe or other format)
            video_info = self._parse_notifyme_message(message)
            
            if video_info:
                # This is a NotifyMe or similar message format
                url = video_info["url"]
                print(f"Extracted YouTube URL from message: {url}")
            else:
                # Treat the message as a direct YouTube URL as fallback
                url = message
                print(f"No URL found in message, treating as direct URL: {url}")
        
        # Extract video ID
        video_id = extract_video_id(url)
        
        if not video_id:
            print(f"No valid YouTube URL found in message: {message}")
            return False
        
        # Check if this is a YouTube Short and skip if so (more robust check)
        is_short = False
        
        # Check URL for /shorts/ pattern
        if '/shorts/' in url.lower():
            is_short = True
        
        # Additional check for shorts format video IDs (typically starts with specific patterns)
        if not is_short:
            try:
                # Try to get video metadata to confirm if it's a short
                import requests
                metadata_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                response = requests.get(metadata_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Check title and author name for "#shorts" tag
                    if '#shorts' in data.get('title', '').lower() or '#shorts' in data.get('author_name', '').lower():
                        is_short = True
                    # Check video dimensions - shorts are typically vertical (height > width)
                    elif 'height' in data and 'width' in data and data['height'] > data['width']:
                        is_short = True
            except Exception as e:
                print(f"Error checking if video is a short: {e}")
                
        if is_short:
            print(f"Skipping YouTube Short: {url}")
            return True  # Return True to indicate successful handling (skipping shorts is expected behavior)
            
        # Check if this is a live stream and skip if so
        if is_youtube_live(video_id):
            print(f"Skipping YouTube Live stream: {url}")
            return True  # Return True to indicate successful handling
        
        # Check if this video has already been processed
        if video_id in self.processed_videos and not force:
            print(f"Video {video_id} has already been processed, skipping")
            return True  # Return True since this is normal behavior, not an error
            
        print(f"Processing video {video_id}")
        
        try:
            # Load config to get OpenAI API key
            try:
                with open("data/config.json", "r") as f:
                    config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                print("No config file found or invalid JSON")
                return False
                
            api_key = config.get("openai_api_key", "")
            if not api_key:
                print("No OpenAI API key found in config")
                return False
            
            # Extract video information from the URL
            video_info = {
                "video_id": video_id,
                "url": url,
                "channel_name": ""
            }
            
            # Try to get channel name from metadata
            try:
                import requests
                metadata_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                response = requests.get(metadata_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    video_info["channel_name"] = data.get("author_name", "")
                    if "title" not in video_info:
                        video_info["title"] = data.get("title", "")
            except Exception as e:
                print(f"Error getting video metadata: {e}")
            
            # Get transcript
            print(f"Getting transcript for video {video_id}")
            transcript = await get_transcript(url)
            
            if not transcript:
                print(f"Failed to retrieve transcript for video {video_id}")
                return False
            
            # Save transcript to file
            transcript_file = self._save_transcript_to_file(video_id, transcript)
            print(f"Saved transcript to {transcript_file}")
            
            # Generate summary
            print(f"Generating summary for video {video_id}")
            summary = await chunk_and_summarize(transcript, api_key)
            
            # Handle case where summary generation failed
            if not summary:
                print(f"Failed to generate summary for video {video_id}")
                
                # Create a basic fallback summary
                summary = {
                    "title": "Video Summary (Generation Failed)",
                    "points": [
                        "The AI model could not generate a summary for this video",
                        "This could be due to API limitations or content complexity",
                        "The full transcript is still available"
                    ],
                    "summary": "Summary generation failed. Please check the transcript for the full content."
                }
            
            # Save summary to file
            summary_file = self._save_summary_to_file(video_id, summary)
            
            # Save to summaries.json
            self._save_processed_video(video_id, summary, message)
            
            # Send transcript and summary to Discord channels
            webhooks = config.get("webhooks", {})
            
            # First, send the notification in the standardized format to the uploads channel
            if "yt_uploads" in webhooks and webhooks["yt_uploads"]:
                try:
                    # Determine channel name - either from video_info or summary title
                    channel_name = video_info["channel_name"] if video_info else summary.get("title", "").split(" - ")[0]
                    video_title = summary.get("title", "New Video")
                    
                    # Create a better formatted notification with bold channel name and improved formatting
                    # Use Discord embed for better presentation and link preview
                    await send_discord_message(
                        webhooks["yt_uploads"],
                        title=f"🎬 New Video Upload",
                        description=f"**{channel_name}** just posted a new video!\n\n**[{video_title}](https://www.youtube.com/watch?v={video_id})**",
                        color=16711680,  # Red color for YouTube
                        thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    )
                except Exception as e:
                    print(f"Error sending notification to Discord: {e}")
            
            # Send transcript to transcript channel
            if "yt_transcripts" in webhooks and webhooks["yt_transcripts"]:
                try:
                    print(f"Sending transcript for video {video_id} to Discord...")
                    with open(transcript_file, "r") as f:
                        transcript_content = f.read()
                    
                    # Use video title for filename
                    safe_title = sanitize_filename(summary.get('title', f'video_{video_id}'))
                    filename = f"{safe_title}_transcript.txt"
                    
                    # Send as a file without video link
                    await send_file_to_discord(
                        webhooks["yt_transcripts"],
                        transcript_content,
                        filename,
                        f"📝 **Transcript for:** {summary.get('title', 'Unknown Video')}"
                    )
                except Exception as e:
                    print(f"Error sending transcript to Discord: {e}")
            
            # Send summary to summaries channel
            if "yt_summaries" in webhooks and webhooks["yt_summaries"]:
                try:
                    print(f"Sending summary for video {video_id} to Discord...")
                    
                    # Format points with better bullets and spacing for Discord
                    points_formatted = ""
                    if summary.get("points"):
                        points_formatted = "\n".join([f"• {point}" for point in summary.get("points", [])])
                    
                    # Format noteworthy mentions if available
                    mentions_formatted = ""
                    if summary.get("noteworthy_mentions") and len(summary.get("noteworthy_mentions")) > 0:
                        mentions_formatted = "\n".join([f"• {point}" for point in summary.get("noteworthy_mentions", [])])
                    
                    # Create a clean, well-formatted message
                    summary_text = summary.get("summary", "No summary available")
                    verdict = summary.get("verdict", "")
                    
                    # Create Discord embed description without video link
                    description = ""
                    
                    if verdict:
                        description += f"**Verdict:** {verdict}\n\n"
                    
                    # Keep the main summary text short in the embed
                    if len(summary_text) > 1000:
                        description += f"**Summary:**\n{summary_text[:1000]}...\n\n"
                    else:
                        description += f"**Summary:**\n{summary_text}\n\n"
                    
                    # Create fields with improved formatting
                    fields = []
                    
                    if points_formatted:
                        fields.append({"name": "📊 Key Points", "value": points_formatted})
                    
                    if mentions_formatted:
                        fields.append({"name": "🔍 Noteworthy Mentions", "value": mentions_formatted})
                    
                    # Send embed message with better color and title formatting
                    await send_discord_message(
                        webhooks["yt_summaries"],
                        title=f"📺 {summary.get('title', 'Video Summary')}",
                        description=description,
                        fields=fields,
                        color=3447003  # Discord blue color
                    )
                    
                    # Also send the full formatted summary as a file
                    with open(summary_file, "r") as f:
                        summary_content = f.read()
                    
                    # Use video title for filename
                    safe_title = sanitize_filename(summary.get('title', f'video_{video_id}'))
                    filename = f"{safe_title}_summary.txt"
                    
                    await send_file_to_discord(
                        webhooks["yt_summaries"],
                        summary_content,
                        filename
                    )
                except Exception as e:
                    print(f"Error sending summary to Discord: {e}")
            
            print(f"Successfully processed video {video_id}")
            return True
            
        except Exception as e:
            print(f"Error processing video {video_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _save_transcript_to_file(self, video_id, transcript):
        """Save transcript text to a file with video title as filename"""
        try:
            # Get video title for filename
            from .transcript import get_video_info
            video_info = get_video_info(f"https://www.youtube.com/watch?v={video_id}")
            
            if video_info and video_info.get('title'):
                safe_title = sanitize_filename(video_info['title'])
                filename = f"{safe_title}.txt"
            else:
                filename = f"{video_id}.txt"
            
            # Create transcripts directory if it doesn't exist
            transcripts_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'transcripts')
            os.makedirs(transcripts_dir, exist_ok=True)
            
            filepath = os.path.join(transcripts_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            return filepath
        except Exception as e:
            print(f"Error saving transcript to file: {e}")
            # Fallback to video ID filename
            transcripts_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'transcripts')
            os.makedirs(transcripts_dir, exist_ok=True)
            filepath = os.path.join(transcripts_dir, f"{video_id}.txt")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            return filepath
    
    def _save_summary_to_file(self, video_id, summary):
        """Save summary to a file with video title as filename"""
        try:
            # Use title from summary if available
            if summary.get('title'):
                safe_title = sanitize_filename(summary['title'])
                filename = f"{safe_title}.txt"
            else:
                filename = f"{video_id}.txt"
            
            # Create summaries directory if it doesn't exist
            summaries_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'summaries')
            os.makedirs(summaries_dir, exist_ok=True)
            
            filepath = os.path.join(summaries_dir, filename)
            
            # Format summary as readable text
            summary_text = f"Title: {summary.get('title', 'Unknown')}\n\n"
            
            if summary.get('points'):
                summary_text += "Key Points:\n"
                for i, point in enumerate(summary['points'], 1):
                    summary_text += f"{i}. {point}\n"
                summary_text += "\n"
            
            if summary.get('summary'):
                summary_text += f"Summary:\n{summary['summary']}\n\n"
            
            if summary.get('noteworthy_mentions'):
                summary_text += "Noteworthy Mentions:\n"
                for mention in summary['noteworthy_mentions']:
                    summary_text += f"- {mention}\n"
                summary_text += "\n"
            
            if summary.get('verdict'):
                summary_text += f"Verdict: {summary['verdict']}\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(summary_text)
            
            return filepath
        except Exception as e:
            print(f"Error saving summary to file: {e}")
            # Fallback to video ID filename
            summaries_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'summaries')
            os.makedirs(summaries_dir, exist_ok=True)
            filepath = os.path.join(summaries_dir, f"{video_id}.txt")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(summary))
            
            return filepath

    async def start(self):
        """Start listening for new messages"""
        print("Starting Discord listener...")
        
        while True:
            # In a real implementation, this would listen for webhooks or use a Discord bot
            # For this prototype, we just sleep and check periodically
            # You would replace this with actual Discord API integration
            
            print("Checking for new messages...")
            
            # Simulate checking for new messages
            # In a real implementation, this would be replaced with actual Discord API calls
            
            await asyncio.sleep(60)  # Check every 60 seconds
    
    async def process_latest_message(self, force=True):
        """Process the latest message (for manual trigger)"""
        print("Manual trigger requested - attempting to process latest YouTube link")
        
        # For testing/demo purposes, use a hardcoded test URL
        # In a real implementation, you would fetch the latest message from the Discord API
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
        
        print(f"Processing test video URL: {test_url}")
        return await self.process_message(test_url, force=force) 