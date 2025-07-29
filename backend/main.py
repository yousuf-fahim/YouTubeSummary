import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

# Add the parent directory to the path to import shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Import shared modules
from shared.youtube_tracker import YouTubeTracker
from shared.transcript import get_transcript
from shared.summarize import summarize_content, generate_daily_report
from shared.discord_utils import send_discord_message
from shared.supabase_utils import get_supabase_client
from shared.config_service import ConfigService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Summary Bot API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
tracker = None
scheduler = None
config_service = ConfigService()

class VideoRequest(BaseModel):
    url: str
    channel_id: Optional[str] = None

class ChannelRequest(BaseModel):
    channel_id: str
    channel_name: str

class ProcessingResponse(BaseModel):
    success: bool
    message: str
    video_id: Optional[str] = None

class MonitoringResponse(BaseModel):
    success: bool
    message: str
    channels_count: int
    last_check: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    global tracker, scheduler
    
    try:
        # Initialize YouTube tracker
        tracker = YouTubeTracker()
        
        # Initialize scheduler
        scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Berlin'))
        
        # Add daily report job at 18:00 CEST
        scheduler.add_job(
            generate_daily_report_job,
            CronTrigger(hour=18, minute=0, timezone=pytz.timezone('Europe/Berlin')),
            id='daily_report',
            replace_existing=True
        )
        
        # Add channel monitoring job every 30 minutes
        scheduler.add_job(
            monitor_channels_job,
            CronTrigger(minute='*/30', timezone=pytz.timezone('Europe/Berlin')),
            id='channel_monitoring',
            replace_existing=True
        )
        
        # Start scheduler
        scheduler.start()
        
        logger.info("✅ YouTube Summary Bot API started successfully")
        logger.info("📅 Daily reports scheduled for 18:00 CEST")
        logger.info("🔍 Channel monitoring every 30 minutes")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of the application."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Scheduler stopped")

async def generate_daily_report_job():
    """Background job to generate daily reports."""
    try:
        logger.info("📊 Starting daily report generation...")
        
        # Get summaries from the last 24 hours
        supabase = get_supabase_client()
        if supabase:
            try:
                yesterday = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                response = supabase.table('summaries').select('*').gte('created_at', yesterday.isoformat()).execute()
                summaries = response.data
            except Exception as e:
                logger.warning(f"Supabase query failed, using local data: {e}")
                summaries = []
        else:
            # Fallback to local data
            summaries = []
        
        if summaries:
            # Generate daily report
            report = await generate_daily_report(summaries)
            
            # Send to Discord
            webhook_url = os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
            if webhook_url and report:
                await send_discord_message(webhook_url, report)
                logger.info(f"📈 Daily report sent successfully ({len(summaries)} videos)")
            else:
                logger.warning("⚠️ No webhook URL or empty report")
        else:
            logger.info("📭 No new videos for daily report")
            
    except Exception as e:
        logger.error(f"❌ Daily report generation failed: {str(e)}")

async def monitor_channels_job():
    """Background job to monitor tracked channels for new videos."""
    global tracker
    
    if not tracker:
        logger.warning("⚠️ Tracker not initialized")
        return
    
    try:
        logger.info("🔍 Starting channel monitoring...")
        
        # Get tracked channels
        tracked_channels = tracker.get_tracked_channels()
        
        if not tracked_channels:
            logger.info("📭 No channels being tracked")
            return
        
        new_videos_count = 0
        
        for channel_id, channel_info in tracked_channels.items():
            try:
                # Check for new videos
                new_videos = await tracker.check_for_new_videos(channel_id)
                
                if new_videos:
                    logger.info(f"🎥 Found {len(new_videos)} new videos from {channel_info.get('name', channel_id)}")
                    
                    for video in new_videos:
                        # Process each new video
                        await process_video_background(video['url'], channel_id)
                        new_videos_count += 1
                        
                        # Small delay between processing videos
                        await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Error monitoring channel {channel_id}: {str(e)}")
                continue
        
        if new_videos_count > 0:
            logger.info(f"✅ Processed {new_videos_count} new videos from monitoring")
        else:
            logger.info("📭 No new videos found in monitored channels")
            
    except Exception as e:
        logger.error(f"❌ Channel monitoring failed: {str(e)}")

async def process_video_background(video_url: str, channel_id: Optional[str] = None):
    """Process a video in the background."""
    try:
        logger.info(f"🎬 Processing video: {video_url}")
        
        # Extract video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            logger.error(f"❌ Invalid YouTube URL: {video_url}")
            return
        
        # Get transcript
        transcript_data = await get_transcript(video_id)
        if not transcript_data:
            logger.error(f"❌ Failed to get transcript for video: {video_id}")
            return
        
        # Generate summary
        summary = await summarize_content(
            transcript_data['content'],
            transcript_data.get('title', 'Unknown Title'),
            video_url
        )
        
        if not summary:
            logger.error(f"❌ Failed to generate summary for video: {video_id}")
            return
        
        # Send to Discord channels
        await send_to_discord_channels(video_url, transcript_data, summary)
        
        logger.info(f"✅ Successfully processed video: {video_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing video {video_url}: {str(e)}")

async def send_to_discord_channels(video_url: str, transcript_data: dict, summary: str):
    """Send processed video data to Discord channels."""
    try:
        # Send original URL to uploads channel
        uploads_webhook = os.getenv('DISCORD_UPLOADS_WEBHOOK')
        if uploads_webhook:
            await send_discord_message(uploads_webhook, f"🎥 **New Video Processed:**\n{video_url}")
        
        # Send transcript to transcripts channel (truncated if too long)
        transcripts_webhook = os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK')
        if transcripts_webhook:
            transcript_msg = f"📄 **Transcript for:** {transcript_data.get('title', 'Unknown')}\n\n"
            transcript_content = transcript_data['content']
            
            # Discord has a 2000 character limit, so truncate if necessary
            if len(transcript_msg + transcript_content) > 1900:
                available_space = 1900 - len(transcript_msg) - 50  # 50 chars for "..."
                transcript_content = transcript_content[:available_space] + "...\n\n[Content truncated]"
            
            transcript_msg += transcript_content
            await send_discord_message(transcripts_webhook, transcript_msg)
        
        # Send summary to summaries channel
        summaries_webhook = os.getenv('DISCORD_SUMMARIES_WEBHOOK')
        if summaries_webhook:
            summary_msg = f"📊 **Summary for:** {transcript_data.get('title', 'Unknown')}\n\n{summary}"
            await send_discord_message(summaries_webhook, summary_msg)
            
    except Exception as e:
        logger.error(f"❌ Error sending to Discord: {str(e)}")

def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    import re
    
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "YouTube Summary Bot API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "process_video": "/process",
            "add_channel": "/channels/add",
            "remove_channel": "/channels/remove",
            "list_channels": "/channels",
            "monitoring_status": "/monitoring/status",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global tracker, scheduler
    
    status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "tracker": tracker is not None,
            "scheduler": scheduler is not None and scheduler.running,
            "supabase": get_supabase_client() is not None
        }
    }
    
    return status

@app.post("/process", response_model=ProcessingResponse)
async def process_video(request: VideoRequest, background_tasks: BackgroundTasks):
    """Process a single YouTube video."""
    try:
        video_id = extract_video_id(request.url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        # Add to background tasks
        background_tasks.add_task(process_video_background, request.url, request.channel_id)
        
        return ProcessingResponse(
            success=True,
            message="Video processing started",
            video_id=video_id
        )
        
    except Exception as e:
        logger.error(f"❌ Error in process_video endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/channels/add")
async def add_channel(request: ChannelRequest):
    """Add a channel to tracking."""
    global tracker
    
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    
    try:
        success = tracker.add_channel(request.channel_id, request.channel_name)
        
        if success:
            return {"success": True, "message": f"Channel {request.channel_name} added successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add channel")
            
    except Exception as e:
        logger.error(f"❌ Error adding channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/channels/remove")
async def remove_channel(request: ChannelRequest):
    """Remove a channel from tracking."""
    global tracker
    
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    
    try:
        success = tracker.remove_channel(request.channel_id)
        
        if success:
            return {"success": True, "message": f"Channel removed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Channel not found")
            
    except Exception as e:
        logger.error(f"❌ Error removing channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channels")
async def list_channels():
    """List all tracked channels."""
    global tracker
    
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    
    try:
        channels = tracker.get_tracked_channels()
        
        return {
            "success": True,
            "channels": channels,
            "count": len(channels)
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing channels: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/status", response_model=MonitoringResponse)
async def monitoring_status():
    """Get monitoring status."""
    global tracker, scheduler
    
    try:
        channels_count = 0
        last_check = None
        
        if tracker:
            channels = tracker.get_tracked_channels()
            channels_count = len(channels)
        
        if scheduler and scheduler.running:
            # Get last execution time of monitoring job
            job = scheduler.get_job('channel_monitoring')
            if job and hasattr(job, 'next_run_time'):
                last_check = job.next_run_time.isoformat() if job.next_run_time else None
        
        return MonitoringResponse(
            success=True,
            message="Monitoring system operational",
            channels_count=channels_count,
            last_check=last_check
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting monitoring status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/trigger")
async def trigger_monitoring():
    """Manually trigger channel monitoring."""
    try:
        # Run monitoring in background
        asyncio.create_task(monitor_channels_job())
        
        return {"success": True, "message": "Channel monitoring triggered"}
        
    except Exception as e:
        logger.error(f"❌ Error triggering monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reports/trigger")
async def trigger_daily_report():
    """Manually trigger daily report generation."""
    try:
        # Run report generation in background
        asyncio.create_task(generate_daily_report_job())
        
        return {"success": True, "message": "Daily report generation triggered"}
        
    except Exception as e:
        logger.error(f"❌ Error triggering daily report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
