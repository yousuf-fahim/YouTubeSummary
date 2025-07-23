import os
import json
import time
import asyncio
import re
from datetime import datetime

from transcript import get_transcript, extract_video_id
from summarize import chunk_and_summarize
from discord_utils import send_discord_message, send_file_to_discord

class DiscordListener:
    def __init__(self):
        self.processed_videos = self._load_processed_videos()
        self.last_check_time = time.time()
        
        # Create directories if they don't exist
        os.makedirs("data/transcripts", exist_ok=True)
        os.makedirs("data/summaries", exist_ok=True)
        
        print(f"Discord listener initialized with {len(self.processed_videos)} processed videos")
    
    def _load_processed_videos(self):
        """Load list of already processed video IDs"""
        try:
            with open("data/summaries.json", "r") as f:
                summaries = json.load(f)
                # Extract video IDs from the summaries
                processed = set()
                for date, videos in summaries.items():
                    for video in videos:
                        if "video_id" in video:
                            processed.add(video["video_id"])
                return processed
        except (FileNotFoundError, json.JSONDecodeError):
            # Create empty file if it doesn't exist
            os.makedirs("data", exist_ok=True)
            with open("data/summaries.json", "w") as f:
                json.dump({}, f)
            return set()
    
    def _save_processed_video(self, video_id, summary, url):
        """Save a processed video to summaries.json"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with open("data/summaries.json", "r") as f:
                try:
                    summaries = json.load(f)
                except json.JSONDecodeError:
                    summaries = {}
        except FileNotFoundError:
            summaries = {}
            
        if today not in summaries:
            summaries[today] = []
            
        video_summary = {
            "video_id": video_id,
            "url": url,
            **summary
        }
        
        summaries[today].append(video_summary)
        
        with open("data/summaries.json", "w") as f:
            json.dump(summaries, f, indent=2)
            
        # Add to in-memory set
        self.processed_videos.add(video_id)
    
    def _save_transcript_to_file(self, video_id, transcript):
        """Save transcript to a file"""
        filename = f"data/transcripts/{video_id}.txt"
        with open(filename, "w") as f:
            f.write(transcript)
        return filename
    
    def _save_summary_to_file(self, video_id, summary):
        """Save formatted summary to a file"""
        filename = f"data/summaries/{video_id}.txt"
        
        # Format the summary for the file
        title = summary.get("title", "Video Summary")
        points = summary.get("points", [])
        summary_text = summary.get("summary", "No summary text available")
        
        formatted_summary = f"# {title}\n\n"
        formatted_summary += "## Key Points\n\n"
        
        for point in points:
            formatted_summary += f"* {point}\n"
            
        formatted_summary += f"\n## Summary\n\n{summary_text}\n"
        
        with open(filename, "w") as f:
            f.write(formatted_summary)
        
        return filename
    
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
        Process a YouTube video URL from a Discord message
        
        Args:
            message (str): The Discord message content (YouTube URL or NotifyMe message)
            force (bool): Whether to force processing even if the video was processed before
        """
        print(f"Processing message: {message}")
        
        # First check if this is a NotifyMe bot message
        video_info = self._parse_notifyme_message(message)
        
        if video_info:
            # This is a NotifyMe message, extract the YouTube URL
            url = video_info["url"]
            print(f"Detected NotifyMe bot message with video: {url}")
        else:
            # Treat the message as a direct YouTube URL
            url = message
        
        # Extract video ID
        video_id = extract_video_id(url)
        
        if not video_id:
            print(f"No valid YouTube URL found in message: {message}")
            return False
        
        # Check if this video has already been processed
        if video_id in self.processed_videos and not force:
            print(f"Video {video_id} has already been processed, skipping")
            return False
            
        print(f"Processing video {video_id}")
        
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
        
        # Send transcript to transcript channel
        if "yt_transcripts" in webhooks and webhooks["yt_transcripts"]:
            print(f"Sending transcript for video {video_id} to Discord...")
            with open(transcript_file, "r") as f:
                transcript_content = f.read()
            
            # Send as a file
            await send_file_to_discord(
                webhooks["yt_transcripts"],
                transcript_content,
                f"{video_id}_transcript.txt",
                f"📝 **Transcript for:** {url}"
            )
        
        # Send summary to summaries channel
        if "yt_summaries" in webhooks and webhooks["yt_summaries"]:
            print(f"Sending summary for video {video_id} to Discord...")
            
            # Send an embed with key information
            title = summary.get("title", "Video Summary")
            summary_text = summary.get("summary", "No summary available")
            points = summary.get("points", [])
            
            # Prepare fields for Discord embed
            fields = [
                {"name": "📊 Key Points", "value": "\n".join([f"• {point}" for point in points[:5]])}
            ]
            
            # Send embed message
            await send_discord_message(
                webhooks["yt_summaries"],
                title=f"📺 {title}",
                description=summary_text[:2000] if summary_text else "No summary text available",
                fields=fields,
                content=f"🎬 **Summary for:** {url}"
            )
            
            # Also send the full formatted summary as a file
            with open(summary_file, "r") as f:
                summary_content = f.read()
            
            await send_file_to_discord(
                webhooks["yt_summaries"],
                summary_content,
                f"{video_id}_summary.txt"
            )
        
        print(f"Successfully processed video {video_id}")
        return True
    
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
        
    async def process_latest_notifyme_message(self, force=True):
        """Process the latest NotifyMe bot message (for manual trigger)"""
        print("Manual trigger requested - attempting to process latest NotifyMe YouTube notification")
        
        # Simulate a NotifyMe message for testing/demo purposes
        test_notifyme_message = """
        NotifyMe APP 21/7/25, 2:51PM
        Iman Gadzhi just posted a new video!
        youtu.be/US47EpxBVHk
        YouTube
        Iman Gadzhi
        Build A One-Person Business As A Beginner (From $0 To $10K)
        """
        
        print(f"Processing NotifyMe message: {test_notifyme_message}")
        return await self.process_message(test_notifyme_message, force=force) 