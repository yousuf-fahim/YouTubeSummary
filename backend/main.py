#!/usr/bin/env python3
"""
Simplified YouTube Summary Bot Backend
A clean, focused FastAPI server for YouTube video processing
"""

import os
import sys
import asyncio
import re
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import only what we need
from shared.transcript import get_transcript, extract_video_id
from shared.summarize import chunk_and_summarize
from shared.discord_utils import send_discord_message
from shared.supabase_utils import (
    get_tracked_channels, 
    save_tracked_channel, 
    delete_tracked_channel,
    get_all_summaries
)
from shared.youtube_tracker import check_tracked_channels, get_latest_videos_from_channel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

# Automated monitoring function
async def automated_channel_monitoring():
    """Check all tracked channels for new videos and process them"""
    try:
        logger.info("🔄 Starting automated channel monitoring...")
        
        # Get all tracked channels
        channels_data = get_tracked_channels()
        tracked_channels = channels_data.get("tracked_channels", [])
        
        if not tracked_channels:
            logger.info("📭 No channels to monitor")
            return
        
        logger.info(f"📊 Monitoring {len(tracked_channels)} channels")
        
        # Check each channel for new videos
        new_videos_found = 0
        
        for channel in tracked_channels:
            try:
                latest_video = get_latest_videos_from_channel(channel)
                
                if latest_video:
                    video_id = latest_video.get('id')
                    video_title = latest_video.get('title', 'Unknown Title')
                    
                    # Check if we've already processed this video
                    # (You could add a database check here if needed)
                    
                    logger.info(f"📹 Found latest video from {channel}: {video_title}")
                    
                    # Process the video automatically
                    try:
                        # The video_id is already extracted from RSS, so we can use it directly
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        result = await process_video_internal(video_url)
                        if result["success"]:
                            new_videos_found += 1
                            logger.info(f"✅ Successfully processed: {video_title}")
                        else:
                            logger.error(f"❌ Failed to process: {video_title} - {result.get('error')}")
                    except Exception as e:
                        logger.error(f"❌ Error processing video {video_id}: {str(e)}")
                
            except Exception as e:
                logger.error(f"❌ Error checking channel {channel}: {str(e)}")
        
        logger.info(f"🎯 Automated monitoring complete. Processed {new_videos_found} new videos")
        
    except Exception as e:
        logger.error(f"❌ Error in automated monitoring: {str(e)}")

def start_scheduler():
    """Start the automated scheduler"""
    global scheduler
    
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        
        # Add job to run every 30 minutes
        scheduler.add_job(
            automated_channel_monitoring,
            IntervalTrigger(minutes=30),
            id='channel_monitoring',
            name='Automated Channel Monitoring',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("⏰ Automated scheduler started - checking channels every 30 minutes")
    else:
        logger.info("⏰ Scheduler already running")

def stop_scheduler():
    """Stop the automated scheduler"""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("⏹️ Scheduler stopped")
    else:
        logger.info("⏹️ Scheduler was not running")

async def process_video_internal(video_url_or_id: str) -> dict:
    """Internal function to process a video (used by scheduler and API)"""
    try:
        # Extract video ID if full URL provided, or use as-is if already an ID
        if "youtube.com" in video_url_or_id or "youtu.be" in video_url_or_id:
            video_id = extract_video_id(video_url_or_id)
            if not video_id:
                return {"success": False, "error": "Invalid YouTube URL"}
        else:
            # Assume it's already a video ID
            video_id = video_url_or_id
            # Validate it looks like a YouTube video ID (11 characters, alphanumeric + _ -)
            if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                return {"success": False, "error": "Invalid YouTube video ID format"}
        
        logger.info(f"🎬 Processing video: {video_id}")
        
        # Construct full URL for transcript extraction
        full_video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Get transcript
        transcript_result = await get_transcript(full_video_url)
        
        # Handle different return types from get_transcript
        if transcript_result is None:
            return {"success": False, "error": "Failed to get transcript - function returned None"}
        elif isinstance(transcript_result, dict):
            if not transcript_result.get("success"):
                return {"success": False, "error": f"Failed to get transcript: {transcript_result.get('error')}"}
            transcript_text = transcript_result.get("transcript", "")
        else:
            # If it's a string (old format)
            transcript_text = transcript_result
        
        if not transcript_text:
            return {"success": False, "error": "Empty transcript received"}
        
        # Generate summary
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured"}
        
        summary_result = await chunk_and_summarize(transcript_text, openai_api_key, video_id)
        
        # Handle different return formats from chunk_and_summarize
        if summary_result is None:
            return {"success": False, "error": "Failed to generate summary - function returned None"}
        elif isinstance(summary_result, dict):
            if "success" in summary_result and not summary_result.get("success"):
                return {"success": False, "error": f"Failed to generate summary: {summary_result.get('error')}"}
            # Extract summary text from the response
            summary_text = summary_result.get("summary", "") or summary_result.get("summary_text", "")
        else:
            # If it's a string (old format)
            summary_text = str(summary_result)
        
        if not summary_text:
            return {"success": False, "error": "Empty summary received"}
        
        # Send to Discord if webhooks are configured
        try:
            # Get Discord webhook URL from environment
            webhook_url = os.getenv("DISCORD_SUMMARIES_WEBHOOK")
            if webhook_url:
                discord_result = await send_discord_message(
                    webhook_url=webhook_url,
                    title="🤖 New Video Processed Automatically!",
                    description=f"**Video:** https://www.youtube.com/watch?v={video_id}\n\n**Summary:**\n{summary_text[:1500]}{'...' if len(summary_text) > 1500 else ''}",
                    color=0x00ff00  # Green color for success
                )
                logger.info(f"📤 Sent summary to Discord: {discord_result}")
            else:
                logger.info("📤 No Discord webhook configured, skipping notification")
        except Exception as e:
            logger.warning(f"⚠️ Discord notification failed: {str(e)}")
        
        logger.info(f"✅ Successfully processed video: {video_id}")
        
        return {
            "success": True,
            "video_id": video_id,
            "summary": summary_text,
            "message": "Video processed successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing video: {str(e)}")
        return {"success": False, "error": str(e)}

# Create FastAPI app
app = FastAPI(title="YouTube Summary Bot API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to initialize scheduler
@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    logger.info("🚀 Starting YouTube Summary Bot API...")
    
    # Start the automated scheduler
    start_scheduler()
    
    logger.info("✅ Application startup complete")

# Shutdown event to cleanup scheduler
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("🛑 Shutting down application...")
    
    # Stop the scheduler
    stop_scheduler()
    
    logger.info("✅ Application shutdown complete")

# Request Models
class VideoProcessRequest(BaseModel):
    youtube_url: str

class ChannelRequest(BaseModel):
    channel_id: str
    channel_name: str = ""

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_SUMMARIES = os.getenv("DISCORD_WEBHOOK_SUMMARIES")

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "service": "YouTube Summary Bot API",
        "version": "2.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "openai_configured": bool(OPENAI_API_KEY),
            "discord_configured": bool(DISCORD_WEBHOOK_SUMMARIES)
        }
    }

@app.get("/api/health")
async def api_health_check():
    """API health check endpoint (for frontend compatibility)"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "openai_configured": bool(OPENAI_API_KEY),
            "discord_configured": bool(DISCORD_WEBHOOK_SUMMARIES)
        }
    }

@app.post("/api/process-video")
async def process_video(request: VideoProcessRequest):
    """
    Process a YouTube video: extract transcript, generate summary, send to Discord
    """
    try:
        result = await process_video_internal(request.youtube_url)
        
        if result["success"]:
            return {
                "status": "success",
                "video_id": result["video_id"],
                "summary": result["summary"],
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/api/channels")
async def get_channels():
    """Get all tracked channels"""
    try:
        channels_data = get_tracked_channels()  # This returns a dict with tracked_channels key
        
        # Ensure we return the expected format
        if isinstance(channels_data, dict):
            tracked_channels = channels_data.get("tracked_channels", [])
            last_videos = channels_data.get("last_videos", {})
        else:
            tracked_channels = channels_data if isinstance(channels_data, list) else []
            last_videos = {}
        
        return {
            "status": "success",
            "tracked_channels": tracked_channels,
            "last_videos": last_videos,
            "count": len(tracked_channels)
        }
    except Exception as e:
        logger.error(f"Error getting channels: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/channels/add")
async def add_channel(request: dict):
    """Add a channel to tracking"""
    try:
        channel_input = request.get("channel_input")
        if not channel_input:
            raise HTTPException(status_code=400, detail="channel_input is required")
        
        # Extract channel ID from URL or use as-is if it's already an ID
        if "youtube.com" in channel_input:
            # Extract channel ID from URL
            if "/@" in channel_input:
                # Handle @username format
                channel_id = channel_input.split("/@")[-1]
            elif "/channel/" in channel_input:
                # Handle /channel/UC... format
                channel_id = channel_input.split("/channel/")[-1]
            else:
                channel_id = channel_input
        else:
            channel_id = channel_input
        
        save_tracked_channel(channel_id)
        return {
            "success": True,
            "status": "success",
            "message": f"Channel {channel_id} added to tracking"
        }
    except Exception as e:
        logger.error(f"Error adding channel: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.delete("/api/channels/{channel_id}")
async def remove_channel(channel_id: str):
    """Remove a channel from tracking"""
    try:
        delete_tracked_channel(channel_id)  # Remove await
        return {
            "status": "success",
            "message": f"Channel {channel_id} removed from tracking"
        }
    except Exception as e:
        logger.error(f"Error removing channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/summaries")
async def get_summaries():
    """Get all video summaries"""
    try:
        summaries = get_all_summaries()  # Remove await
        return {
            "status": "success",
            "summaries": summaries,
            "count": len(summaries)
        }
    except Exception as e:
        logger.error(f"Error getting summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/monitor/status")
async def get_monitoring_status():
    """Get current monitoring and scheduler status"""
    global scheduler
    
    try:
        # Get tracked channels
        channels_data = get_tracked_channels()
        tracked_channels = channels_data.get("tracked_channels", [])
        
        # Check scheduler status
        scheduler_running = scheduler is not None and scheduler.running
        next_run = None
        
        if scheduler_running:
            try:
                jobs = scheduler.get_jobs()
                if jobs:
                    next_run = jobs[0].next_run_time.isoformat() if jobs[0].next_run_time else None
            except:
                pass
        
        return {
            "success": True,
            "monitoring": {
                "channels_tracked": len(tracked_channels),
                "channels": tracked_channels,
                "scheduler_running": scheduler_running,
                "next_check": next_run,
                "check_interval": "30 minutes"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting monitor status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/monitor/start")
async def start_monitoring():
    """Start automated channel monitoring"""
    try:
        start_scheduler()
        return {
            "success": True,
            "message": "Automated monitoring started",
            "check_interval": "30 minutes"
        }
    except Exception as e:
        logger.error(f"Error starting monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/monitor/stop")
async def stop_monitoring():
    """Stop automated channel monitoring"""
    try:
        stop_scheduler()
        return {
            "success": True,
            "message": "Automated monitoring stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/monitor/check-now")
async def check_channels_now():
    """Manually trigger channel checking"""
    try:
        await automated_channel_monitoring()
        return {
            "success": True,
            "message": "Manual channel check completed"
        }
    except Exception as e:
        logger.error(f"Error in manual check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-video")
async def test_video_processing():
    """Test endpoint to process a sample video"""
    # Use a short test video
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll (short and reliable)
    
    try:
        # Extract video ID
        video_id = extract_video_id(test_url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid test video URL")
        
        # Get transcript
        logger.info(f"Testing with video {video_id}")
        transcript_data = await get_transcript(video_id)
        
        if not transcript_data or not transcript_data.get("transcript"):
            return {
                "status": "warning",
                "message": "Test video transcript not available, but system is working",
                "video_id": video_id
            }
        
        # Generate summary (first 500 chars only for testing)
        test_transcript = transcript_data["transcript"][:500] + "..."
        summary = await chunk_and_summarize(
            test_transcript,
            OPENAI_API_KEY,
            title=transcript_data.get("title", "Test Video"),
            channel=transcript_data.get("channel", "Test Channel")
        )
        
        return {
            "status": "success",
            "message": "Video processing test completed successfully",
            "test_data": {
                "video_id": video_id,
                "title": transcript_data.get("title"),
                "channel": transcript_data.get("channel"),
                "summary_preview": summary[:200] + "..." if len(summary) > 200 else summary
            }
        }
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        return {
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "note": "This might be normal - some videos don't have transcripts"
        }

# Simple startup for Heroku
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
