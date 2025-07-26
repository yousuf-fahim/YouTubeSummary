#!/usr/bin/env python3
import os
import json
import asyncio
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from shared.discord_listener import DiscordListener
from schedule import setup_scheduler
from fastapi import FastAPI, Body, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import subprocess
import logging
import requests
from shared.transcript import get_transcript, extract_video_id
from shared.summarize import chunk_and_summarize, generate_daily_report
from shared.discord_utils import send_discord_message, send_file_to_discord
from shared.config_service import ConfigService, AsyncConfigService
from shared.auth_service import AuthService
from shared.constants import SUCCESS_VIDEO_PROCESSED, ERROR_CONFIG_NOT_FOUND
from shared.supabase_utils import get_all_summaries as get_all_supabase_summaries
from shared.supabase_utils import get_tracked_channels, save_tracked_channel, delete_tracked_channel, update_last_video
from shared.youtube_tracker import check_tracked_channels, get_latest_videos_from_channel
from pydantic import BaseModel
from datetime import datetime
import pytz
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Create FastAPI app for the API endpoints
app = FastAPI(title="YouTube Summary Bot API")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "server_time": datetime.now().isoformat()
    }

# Define request models
class ConfigModel(BaseModel):
    openai_api_key: str = ""
    webhooks: dict = {
        "yt_uploads": "",
        "yt_transcripts": "",
        "yt_summaries": "",
        "daily_report": ""
    }

class TestRequestModel(BaseModel):
    youtube_url: str

class ChannelRequestModel(BaseModel):
    channel: str

class WebhookModel(BaseModel):
    content: str = ""
    embeds: list = []
    
# Load config
async def load_config():
    """Load configuration using secure ConfigService"""
    async_config = AsyncConfigService()
    return await async_config.get_config()

# Save config  
async def save_config(config):
    """Save configuration using secure ConfigService - only non-sensitive data"""
    # Note: Sensitive data should be stored in environment variables, not saved here
    print("Warning: Configuration should be managed via environment variables in production")
    return True  # Always return success since we don't store sensitive data

# Auth dependency for webhooks
async def verify_token(request: Request):
    """Verify webhook authentication token using AuthService"""
    return await AuthService.verify_webhook_token(request)

# API endpoints for config
@app.get("/api/config")
async def get_config_endpoint():
    """Get current configuration"""
    return await load_config()

@app.post("/api/config")
async def update_config(config: ConfigModel):
    """Update configuration"""
    current_config = await load_config()
    
    # Update the config with the new values
    updated_config = current_config.copy()
    updated_config["openai_api_key"] = config.openai_api_key
    updated_config["webhooks"] = {
        "yt_uploads": config.webhooks.get("yt_uploads", ""),
        "yt_transcripts": config.webhooks.get("yt_transcripts", ""),
        "yt_summaries": config.webhooks.get("yt_summaries", ""),
        "daily_report": config.webhooks.get("daily_report", "")
    }
    
    await save_config(updated_config)
    return {"status": "success", "message": "Configuration updated successfully"}

@app.post("/api/manual-summary")
async def trigger_manual_summary():
    # To be implemented: trigger summary of latest video
    discord_listener = DiscordListener()
    # Always process the video even if it was already processed before
    result = await discord_listener.process_latest_message(force=True)
    if result:
        return {"status": "success", "message": "Manual summary processed successfully"}
    else:
        return {"status": "error", "message": "Failed to process manual summary"}

@app.post("/api/webhook/notifyme", status_code=200)
async def receive_webhook(webhook_data: dict = Body(...), authorized: bool = Depends(verify_token)):
    """
    Webhook endpoint to receive NotifyMe notifications.
    Configure your Discord webhook to forward NotifyMe messages to this endpoint.
    """
    try:
        # Check if this is a NotifyMe message
        content = webhook_data.get("content", "")
        
        # Parse message from webhook
        if "NotifyMe" in content and "just posted a new video" in content:
            print("Received NotifyMe notification, processing...")
            
            # Process the message
            discord_listener = DiscordListener()
            result = await discord_listener.process_message(content)
            
            if result:
                return {"status": "success", "message": "Video processed successfully"}
            else:
                return {"status": "error", "message": "Failed to process video"}
        
        return {"status": "ignored", "message": "Not a NotifyMe video notification"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": f"Error processing webhook: {str(e)}"}

@app.post("/api/webhook/trigger-daily-report")
async def trigger_daily_report(authorized: bool = Depends(verify_token)):
    """
    Endpoint to trigger the daily report generation.
    Can be called by a cron job or other scheduler.
    """
    try:
        # Load config for API key
        config = await load_config()
        api_key = config.get("openai_api_key")
        daily_report_webhook = config.get("webhooks", {}).get("daily_report")
        
        if not api_key:
            return {"status": "error", "message": "OpenAI API key not configured"}
            
        if not daily_report_webhook:
            return {"status": "error", "message": "Daily report webhook not configured"}
        
        # Load summaries from today
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Try getting summaries from Supabase first
        today_summaries = []
        all_summaries = get_all_supabase_summaries()
        
        if all_summaries:
            # Filter for summaries from today - make timezone aware
            today_date = datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            for summary in all_summaries:
                created_at = datetime.fromisoformat(summary.get("created_at").replace('Z', '+00:00'))
                if created_at >= today_date:
                    # Format summary for the daily report using proper Supabase fields
                    video_id = summary.get("video_id")
                    title = summary.get("title", f"Video {video_id}")
                    points = summary.get("points", [])
                    noteworthy_mentions = summary.get("noteworthy_mentions", [])
                    verdict = summary.get("verdict", "")
                    
                    formatted_summary = {
                        "title": title,
                        "points": points if isinstance(points, list) else [],
                        "summary": summary.get("summary_text", ""),
                        "noteworthy_mentions": noteworthy_mentions if isinstance(noteworthy_mentions, list) else [],
                        "verdict": verdict,
                        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                    }
                    today_summaries.append(formatted_summary)
        
        # If no summaries from Supabase, fall back to local file (legacy support)
        if not today_summaries:
            try:
                with open("data/summaries.json", "r") as f:
                    all_summaries = json.load(f)
                    # Get today's summaries
                    today_summaries = all_summaries.get(today, [])
            except (FileNotFoundError, json.JSONDecodeError):
                today_summaries = []
        
        if not today_summaries:
            print("No summaries found for today")
            today_date = datetime.now().strftime("%A, %B %d, %Y")
            no_videos_message = (
                f"## 📅 Daily Summary Report: {today_date}\n\n"
                f"### 📭 No New Videos Today\n\n"
                f"No new videos were summarized in the past 24 hours.\n\n"
                f"This could be because:\n"
                f"• No new videos were uploaded to tracked channels\n"
                f"• Videos were uploaded but haven't been processed yet\n"
                f"• Videos were shorts or livestreams (which are excluded by default)\n\n"
                f"You can check the channel tracking tab to verify the status of your tracked channels."
            )
            
            await send_discord_message(
                daily_report_webhook,
                title=f"📅 Daily Summary Report: {today_date}",
                description=no_videos_message,
                color=16776960  # Yellow
            )
            return {"status": "success", "message": "No summaries found for today"}
        
        # Generate daily report
        print(f"Generating daily report for {len(today_summaries)} videos")
        report = await generate_daily_report(today_summaries, api_key)
        
        # Send daily report to webhook
        if report:
            await send_discord_message(
                daily_report_webhook,
                title="📅 Daily Summary Report",
                description=report[:2000] if len(report) > 2000 else report,
                color=3447003  # Blue
            )
            
            # If report is too long, also send as a file
            if len(report) > 2000:
                await send_file_to_discord(
                    daily_report_webhook,
                    report,
                    f"daily_report_{today}.txt",
                    content="Full daily report attached as a file due to length."
                )
                
            return {"status": "success", "message": "Daily report generated and sent"}
        else:
            return {"status": "error", "message": "Failed to generate daily report"}
    except Exception as e:
        print(f"Error generating daily report: {e}")
        return {"status": "error", "message": f"Error: {str(e)}"}

@app.post("/api/test")
async def test_pipeline(request: TestRequestModel):
    """Test the transcript and summary pipeline with a specific YouTube URL"""
    print(f"Testing pipeline with URL: {request.youtube_url}")
    
    config = await load_config()
    api_key = config.get("openai_api_key")
    
    if not api_key:
        return {"status": "error", "message": "OpenAI API key not configured"}
    
    # Extract video ID for Supabase integration
    video_id = extract_video_id(request.youtube_url)
    
    # Test transcript extraction
    print("Getting transcript...")
    transcript = await get_transcript(request.youtube_url)
    
    if not transcript:
        return {"status": "error", "message": "Failed to retrieve transcript"}
    
    transcript_preview = transcript[:200] + "..." if len(transcript) > 200 else transcript
    print(f"Transcript retrieved ({len(transcript)} chars): {transcript_preview}")
    
    # Test summary generation with chunking for long transcripts
    print("Generating summary...")
    # Pass video_id to allow Supabase storage
    summary = await chunk_and_summarize(transcript, api_key, video_id)
    
    if not summary:
        return {
            "status": "partial", 
            "message": "Transcript retrieved but summary generation failed",
            "transcript_length": len(transcript),
            "transcript_preview": transcript_preview
        }
    
    return {
        "status": "success",
        "message": "Test completed successfully",
        "transcript_length": len(transcript),
        "transcript_preview": transcript_preview,
        "summary": summary
    }

@app.get("/api/webhook-token")
async def get_webhook_token():
    """Get the current webhook authentication token"""
    config = await load_config()
    token = config.get("webhook_auth_token", "")
    
    if not token:
        # Generate a new token
        token = os.urandom(16).hex()
        config["webhook_auth_token"] = token
        await save_config(config)
        
    return {"token": token}

@app.post("/api/webhook-token/regenerate")
async def regenerate_webhook_token():
    """Regenerate the webhook authentication token"""
    config = await load_config()
    new_token = os.urandom(16).hex()
    config["webhook_auth_token"] = new_token
    await save_config(config)
    
    return {"token": new_token}

@app.post("/api/channels/check/{channel}")
async def check_channel(channel: str):
    """Manually check a YouTube channel for new videos"""
    logger.info(f"Manual check requested for channel: {channel}")
    try:
        # Get latest video from channel
        latest = get_latest_videos_from_channel(channel)
        
        if latest:
            # Format the result
            return {
                "status": "success",
                "video": {
                    "id": latest["id"],
                    "title": latest["title"],
                    "channel": latest["channel_name"],
                    "published": latest["publish_time"],
                    "url": latest["url"]
                }
            }
        else:
            return {
                "status": "error",
                "message": f"Could not fetch latest video from {channel}"
            }
    except Exception as e:
        logger.error(f"Error checking channel {channel}: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/channels/add")
async def add_channel(request: ChannelRequestModel):
    """Add a YouTube channel to track"""
    try:
        channel = request.channel
        # Normalize the channel handle
        if '/' in channel:
            # Extract handle from URL
            match = re.search(r'youtube\.com/(@[^/]+|channel/[^/]+|c/[^/]+)', channel)
            if match:
                channel = match.group(1)
        elif not channel.startswith('@') and not channel.startswith('channel/') and not channel.startswith('c/'):
            channel = '@' + channel
            
        # Load tracking data
        tracking_data = get_tracked_channels()
        tracked_channels = tracking_data.get("tracked_channels", [])
        
        # Check if channel is already tracked
        if channel in tracked_channels:
            return {
                "status": "error",
                "message": f"Channel {channel} is already being tracked"
            }
        
        # Test if channel exists
        test_result = get_latest_videos_from_channel(channel)
        if test_result:
            # Add channel to tracking
            save_tracked_channel(channel)
            
            return {
                "status": "success",
                "message": f"Added {channel} to tracked channels"
            }
        else:
            return {
                "status": "error",
                "message": f"Could not verify channel {channel}"
            }
    except Exception as e:
        logger.error(f"Error adding channel {request.channel}: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/channels")
async def get_channels():
    """Get list of tracked YouTube channels"""
    try:
        tracking_data = get_tracked_channels()
        tracked_channels = tracking_data.get("tracked_channels", [])
        last_videos = tracking_data.get("last_videos", {})
        
        # Format the result - return simple list of channel names for easier frontend handling
        channels = tracked_channels
            
        return {
            "status": "success",
            "channels": channels,
            "last_videos": last_videos
        }
    except Exception as e:
        logger.error(f"Error getting channels: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.delete("/api/channels/{channel}")
async def remove_channel(channel: str):
    """Remove a YouTube channel from tracking"""
    try:
        # Load tracking data
        tracking_data = get_tracked_channels()
        tracked_channels = tracking_data.get("tracked_channels", [])
        
        # Check if channel is tracked
        if channel not in tracked_channels:
            return {
                "status": "error",
                "message": f"Channel {channel} is not being tracked"
            }
        
        # Remove channel from tracking
        delete_tracked_channel(channel)
        
        return {
            "status": "success",
            "message": f"Removed {channel} from tracked channels"
        }
    except Exception as e:
        logger.error(f"Error removing channel {channel}: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

async def process_notification(notification: str):
    """
    Process a notification message about a new YouTube video
    
    Args:
        notification (str): Notification message in the format "{channel} just posted a new video! youtu.be/{video_id}"
        
    Returns:
        bool: True if processed successfully, False otherwise
    """
    try:
        discord_listener = DiscordListener()
        
        # Check if this is a short before processing
        video_id = None
        url_match = re.search(r'youtu\.be\/([a-zA-Z0-9_-]{11})', notification)
        if url_match:
            video_id = url_match.group(1)
        
        # If we can't extract the video ID, just process normally
        if not video_id:
            return await discord_listener.process_message(notification)
            
        # Check if this might be a short before processing
        try:
            metadata_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(metadata_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Check for shorts indicators
                title = data.get('title', '').lower()
                author = data.get('author_name', '').lower()
                
                # Check if it's likely a short
                is_short = False
                if '#shorts' in title or '#short' in title:
                    is_short = True
                elif 'height' in data and 'width' in data and data['height'] > data['width']:
                    is_short = True
                
                if is_short:
                    logger.info(f"Skipping short in automatic processing: {video_id}")
                    # Don't process shorts automatically, but return True as this is expected behavior
                    return True
        except Exception as e:
            logger.error(f"Error checking if video is a short: {e}")
        
        # Process the message normally if it's not detected as a short
        return await discord_listener.process_message(notification)
    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        return False

async def manual_check_channels():
    """
    Manually check tracked channels for new videos
    
    Returns:
        int: Number of new videos found
    """
    try:
        # Create a synchronous wrapper for the async process_notification function
        def process_wrapper(notification):
            # Create a synchronous version of process_notification
            try:
                from shared.discord_listener import DiscordListener
                listener = DiscordListener()
                
                # Extract video URL from notification (handle both dict and string formats)
                if isinstance(notification, dict):
                    url = notification.get('url')
                elif isinstance(notification, str):
                    # If it's a string, treat it as a URL
                    url = notification
                else:
                    logger.error(f"Invalid notification format: {type(notification)}")
                    return False
                
                if url:
                    # Run the processing synchronously by creating a new event loop
                    import asyncio
                    try:
                        # Try to get the current loop
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Create a new loop in a thread for the sync operation
                            import concurrent.futures
                            import threading
                            
                            def run_in_new_loop():
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    return new_loop.run_until_complete(listener.process_message(url))
                                finally:
                                    new_loop.close()
                            
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(run_in_new_loop)
                                return future.result(timeout=300)  # 5 minute timeout
                        else:
                            # No loop running, can use asyncio.run
                            return asyncio.run(listener.process_message(url))
                    except Exception as e:
                        logger.error(f"Error in async processing: {e}")
                        return False
                else:
                    logger.error("No URL found in notification")
                    return False
            except Exception as e:
                logger.error(f"Error in process wrapper: {e}")
                return False
        
        # Check channels
        return check_tracked_channels(process_wrapper)
    except Exception as e:
        logger.error(f"Error checking channels: {e}")
        return 0

@app.post("/api/channels/check-all")
async def check_all_channels():
    """
    Manually trigger a check of all tracked channels
    
    Returns:
        dict: Result of the channel check
    """
    try:
        new_videos = await manual_check_channels()
        return {
            "status": "success",
            "new_videos_count": new_videos,
            "message": f"Found and processed {new_videos} new videos"
        }
    except Exception as e:
        logger.error(f"Error checking all channels: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """
    Get the scheduler status and next report time
    
    Returns:
        dict: Scheduler status information
    """
    try:
        from datetime import datetime, timedelta
        import pytz
        
        # Get CEST timezone
        cest = pytz.timezone('Europe/Paris')
        now = datetime.now(cest)
        
        # Calculate next daily report time (18:00 CEST)
        today_report = now.replace(hour=18, minute=0, second=0, microsecond=0)
        
        if now > today_report:
            # Today's report has passed, next is tomorrow
            next_report = today_report + timedelta(days=1)
        else:
            # Today's report hasn't happened yet
            next_report = today_report
        
        # Calculate time until next report
        time_until = next_report - now
        hours_until = int(time_until.total_seconds() // 3600)
        minutes_until = int((time_until.total_seconds() % 3600) // 60)
        
        return {
            "status": "running",
            "next_daily_report": next_report.isoformat(),
            "time_until_next_report": f"{hours_until}h {minutes_until}m",
            "current_time": now.isoformat(),
            "timezone": "Europe/Paris (CEST)",
            "report_schedule": "Daily at 18:00 CEST"
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/channels/status")
async def get_channels_status():
    """
    Get detailed status of all tracked channels including last check times and latest videos
    
    Returns:
        dict: Detailed channel status information
    """
    try:
        from shared.supabase_utils import get_tracked_channels
        from shared.youtube_tracker import get_latest_videos_from_channel
        
        # Get tracked channels
        tracking_data = get_tracked_channels()
        tracked_channels = tracking_data.get("tracked_channels", [])
        last_videos = tracking_data.get("last_videos", {})
        
        detailed_status = []
        
        for channel in tracked_channels:
            try:
                # Get latest video info
                latest_video = get_latest_videos_from_channel(channel)
                channel_status = {
                    "channel": channel,
                    "is_tracked": True,
                    "last_known_video": last_videos.get(channel, {}),
                    "status": "active"
                }
                
                if latest_video:
                    channel_status["latest_available_video"] = latest_video
                    
                    # Check if there are new videos available
                    last_known_id = last_videos.get(channel, {}).get("id")
                    latest_id = latest_video.get("id") if latest_video else None
                    
                    if last_known_id != latest_id:
                        channel_status["has_new_videos"] = True
                        channel_status["status"] = "new_content_available"
                    else:
                        channel_status["has_new_videos"] = False
                        channel_status["status"] = "up_to_date"
                else:
                    channel_status["status"] = "no_videos_found"
                    channel_status["has_new_videos"] = False
                    
            except Exception as e:
                channel_status = {
                    "channel": channel,
                    "is_tracked": True,
                    "status": "error",
                    "error": str(e),
                    "has_new_videos": False
                }
            
            detailed_status.append(channel_status)
        
        return {
            "status": "success",
            "total_channels": len(tracked_channels),
            "channels": detailed_status,
            "summary": {
                "active": len([c for c in detailed_status if c["status"] == "up_to_date"]),
                "new_content": len([c for c in detailed_status if c["status"] == "new_content_available"]),
                "errors": len([c for c in detailed_status if c["status"] == "error"]),
                "no_videos": len([c for c in detailed_status if c["status"] == "no_videos_found"])
            }
        }
    except Exception as e:
        logger.error(f"Error getting channels status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

async def start_bot():
    """Start the Discord listener and scheduler in the background"""
    discord_listener = DiscordListener()
    
    # Configure the scheduler to send daily reports at 18:00 CEST
    scheduler = setup_scheduler()
    
    # Add job for daily report at 18:00 CEST
    cest = pytz.timezone('Europe/Paris')
    scheduler.add_job(
        trigger_daily_report_task,
        'cron',
        hour=18,
        minute=0,
        timezone=cest,
        id='daily_report',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    
    # Start the Discord listener
    await discord_listener.start()

async def trigger_daily_report_task():
    """Task to trigger the daily report"""
    logger.info("Scheduled daily report triggered")
    try:
        # We need to bypass the auth requirement since this is triggered by the scheduler
        result = await trigger_daily_report(True)
        logger.info(f"Daily report result: {result.get('status', 'unknown')} - {result.get('message', 'No message')}")
        return result
    except Exception as e:
        logger.error(f"Error in daily report task: {e}")
        return {"status": "error", "message": str(e)}

def start_streamlit():
    """Start the Streamlit UI in a separate process"""
    streamlit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", streamlit_path])

async def main():
    # Start the Discord listener and scheduler
    bot_task = asyncio.create_task(start_bot())
    
    # Start the Streamlit UI in a separate process
    start_streamlit()
    
    # Configuration for FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Start FastAPI server
    await server.serve()

if __name__ == "__main__":
    # Run the main function with proper asyncio handling
    asyncio.run(main()) 