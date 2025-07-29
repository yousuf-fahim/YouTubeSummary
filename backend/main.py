import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import json

# Add paths to import shared modules (works both locally and on Heroku)
current_dir = os.path.dirname(__file__)
parent_dir = os.path.join(current_dir, '..')
sys.path.append(current_dir)  # For Heroku deployment (shared in same directory)
sys.path.append(parent_dir)   # For local development (shared in parent directory)

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Import shared modules
from shared.youtube_tracker import YouTubeTracker
from shared.transcript import get_transcript
from shared.summarize import summarize_content, generate_daily_report_wrapper as generate_daily_report
from shared.discord_utils import send_discord_message
from shared.supabase_utils import get_supabase_client
from shared.config_service import ConfigService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Discord commands (import with try/catch to handle missing dependencies)
try:
    from shared.discord_commands import discord_handler
    DISCORD_COMMANDS_ENABLED = True
except ImportError as e:
    logger.warning(f"Discord commands disabled due to missing dependencies: {e}")
    DISCORD_COMMANDS_ENABLED = False

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

class BulkVideoRequest(BaseModel):
    urls: List[str]
    channel_id: Optional[str] = None

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
        summaries = []
        
        if supabase:
            try:
                # Get summaries from last 24 hours (more flexible date range)
                from datetime import datetime, timedelta
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
                
                # Try different table names and structures
                try:
                    response = supabase.table('summaries').select('*').gte('created_at', yesterday).execute()
                    summaries = response.data or []
                    logger.info(f"📊 Found {len(summaries)} summaries from summaries table")
                except Exception as e:
                    logger.warning(f"Summaries table query failed: {e}")
                    
                    # Try transcripts table as fallback
                    try:
                        response = supabase.table('transcripts').select('*').gte('created_at', yesterday).execute()
                        transcripts = response.data or []
                        logger.info(f"📊 Found {len(transcripts)} transcripts as fallback")
                        # Convert transcripts to summary format
                        summaries = [{"title": t.get("title", "Unknown"), "content": t.get("transcript_text", "")[:500]} for t in transcripts]
                    except Exception as e2:
                        logger.warning(f"Transcripts table query also failed: {e2}")
                        
            except Exception as e:
                logger.warning(f"Supabase query failed, using local data: {e}")
                summaries = []
        else:
            logger.warning("⚠️ No Supabase client available")
            # Fallback to local data
            try:
                import os
                summaries_file = os.path.join(os.path.dirname(__file__), 'shared', 'data', 'summaries.json')
                if os.path.exists(summaries_file):
                    with open(summaries_file, 'r') as f:
                        local_data = json.load(f)
                        summaries = local_data.get('summaries', [])
                        logger.info(f"📊 Found {len(summaries)} summaries from local file")
            except Exception as e:
                logger.warning(f"Local summaries fallback failed: {e}")
        
        # Always send a Discord message, even if no videos
        webhook_url = os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
        if webhook_url:
            if summaries:
                # Generate daily report
                report = await generate_daily_report(summaries)
                if report:
                    await send_discord_message(webhook_url, report)
                    logger.info(f"📈 Daily report sent successfully ({len(summaries)} videos)")
                else:
                    # Send fallback message if report generation failed
                    fallback_msg = f"📅 **Daily Report - {datetime.now().strftime('%Y-%m-%d')}**\n\n📊 Found {len(summaries)} videos but report generation failed.\n\n🔧 Please check the summarization service."
                    await send_discord_message(webhook_url, fallback_msg)
                    logger.warning("⚠️ Report generation failed, sent fallback message")
            else:
                # Send "no videos" message
                no_videos_msg = f"📅 **Daily Report - {datetime.now().strftime('%Y-%m-%d')}**\n\n📭 No new videos processed in the last 24 hours.\n\n💡 Add more channels or check if monitoring is working properly."
                await send_discord_message(webhook_url, no_videos_msg)
                logger.info("📭 No videos found - sent daily report with no videos message")
        else:
            logger.error("❌ No DISCORD_DAILY_REPORT_WEBHOOK configured - daily report not sent")
            
    except Exception as e:
        logger.error(f"❌ Daily report generation failed: {str(e)}")
        # Send error notification to Discord if webhook is available
        webhook_url = os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
        if webhook_url:
            try:
                error_msg = f"❌ **Daily Report Error - {datetime.now().strftime('%Y-%m-%d')}**\n\nDaily report generation failed: {str(e)}\n\n🔧 Please check the backend logs."
                await send_discord_message(webhook_url, error_msg)
                logger.info("📧 Error notification sent to Discord")
            except Exception as discord_error:
                logger.error(f"❌ Failed to send error notification to Discord: {discord_error}")

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
        
        # **CRITICAL FIX: Save summary to database**
        await save_summary_to_database(video_id, video_url, transcript_data, summary, channel_id)
        
        # Send to Discord channels
        await send_to_discord_channels(video_url, transcript_data, summary)
        
        logger.info(f"✅ Successfully processed video: {video_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing video {video_url}: {str(e)}")

async def save_summary_to_database(video_id: str, video_url: str, transcript_data: dict, summary: str, channel_id: Optional[str] = None):
    """Save processed video summary to database."""
    try:
        from shared.supabase_utils import save_summary
        
        # Use the correct function signature
        result = save_summary(
            video_id=video_id,
            summary_text=summary,
            title=transcript_data.get('title', 'Unknown Title'),
            video_url=video_url
        )
        
        logger.info(f"✅ Saved summary to database for video: {video_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to save summary to database for {video_id}: {str(e)}")
        # Save to local fallback
        try:
            import json
            fallback_data = {
                "video_id": video_id,
                "video_url": video_url,
                "title": transcript_data.get('title', 'Unknown Title'),
                "summary": summary,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "error": "Database save failed, using local fallback"
            }
            
            # Ensure data directory exists
            os.makedirs("shared/data", exist_ok=True)
            
            # Save to local file
            fallback_file = f"shared/data/summary_{video_id}_{int(datetime.now().timestamp())}.json"
            with open(fallback_file, 'w', encoding='utf-8') as f:
                json.dump(fallback_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved summary to local fallback: {fallback_file}")
            
        except Exception as fallback_error:
            logger.error(f"❌ Even fallback save failed for {video_id}: {str(fallback_error)}")
        
        return None

async def save_summary_locally(summary_data: dict):
    """Save summary to local JSON file as fallback."""
    try:
        import json
        import os
        from pathlib import Path
        
        # Create data directory if it doesn't exist
        data_dir = Path(__file__).parent / 'shared' / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        summaries_file = data_dir / 'summaries.json'
        
        # Load existing summaries
        summaries = {"summaries": []}
        if summaries_file.exists():
            try:
                with open(summaries_file, 'r', encoding='utf-8') as f:
                    summaries = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing summaries: {e}")
                summaries = {"summaries": []}
        
        # Add new summary
        summaries["summaries"].append(summary_data)
        
        # Keep only last 100 summaries to prevent file from growing too large
        if len(summaries["summaries"]) > 100:
            summaries["summaries"] = summaries["summaries"][-100:]
        
        # Save back to file
        with open(summaries_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Summary saved locally for video: {summary_data.get('video_id')}")
        
    except Exception as e:
        logger.error(f"❌ Error saving summary locally: {str(e)}")

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

@app.post("/process/bulk")
async def process_bulk_videos(request: BulkVideoRequest, background_tasks: BackgroundTasks):
    """Process multiple YouTube videos."""
    try:
        logger.info(f"📥 Processing {len(request.urls)} videos in bulk")
        
        if len(request.urls) > 10:  # Limit to prevent abuse
            raise HTTPException(status_code=400, detail="Maximum 10 videos per bulk request")
        
        valid_videos = []
        invalid_urls = []
        
        # Validate all URLs first
        for url in request.urls:
            video_id = extract_video_id(url)
            if video_id:
                valid_videos.append((video_id, url))
            else:
                invalid_urls.append(url)
        
        if not valid_videos:
            raise HTTPException(status_code=400, detail="No valid YouTube URLs provided")
        
        # Add background tasks for all valid videos
        for video_id, url in valid_videos:
            background_tasks.add_task(process_video_background, url, request.channel_id)
        
        response_message = f"Started processing {len(valid_videos)} videos"
        if invalid_urls:
            response_message += f". Skipped {len(invalid_urls)} invalid URLs"
        
        return {
            "success": True,
            "message": response_message,
            "processed_count": len(valid_videos),
            "invalid_count": len(invalid_urls),
            "invalid_urls": invalid_urls
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing bulk videos: {str(e)}")
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

@app.get("/monitoring/status")
async def monitoring_status():
    """Get detailed monitoring status including scheduler information."""
    global tracker, scheduler
    
    try:
        channels_count = 0
        next_monitoring_check = None
        next_daily_report = None
        scheduler_running = False
        
        if tracker:
            channels = tracker.get_tracked_channels()
            channels_count = len(channels)
        
        if scheduler:
            scheduler_running = scheduler.running
            
            # Get next execution times for both jobs
            monitoring_job = scheduler.get_job('channel_monitoring')
            if monitoring_job and hasattr(monitoring_job, 'next_run_time'):
                next_monitoring_check = monitoring_job.next_run_time.isoformat() if monitoring_job.next_run_time else None
            
            report_job = scheduler.get_job('daily_report')
            if report_job and hasattr(report_job, 'next_run_time'):
                next_daily_report = report_job.next_run_time.isoformat() if report_job.next_run_time else None
        
        return {
            "success": True,
            "message": "Monitoring system operational" if scheduler_running else "Scheduler not running",
            "scheduler_running": scheduler_running,
            "channels_count": channels_count,
            "next_monitoring_check": next_monitoring_check,
            "next_daily_report": next_daily_report,
            "monitoring_interval": "Every 30 minutes",
            "report_time": "Daily at 18:00 CEST"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting monitoring status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/channels")
async def get_monitoring_details():
    """Get detailed monitoring information including recent activity."""
    global tracker
    
    try:
        if not tracker:
            raise HTTPException(status_code=500, detail="Tracker not initialized")
        
        channels = tracker.get_tracked_channels()
        
        # Get recent activity (this would be enhanced with actual monitoring data)
        recent_activity = []
        
        return {
            "success": True,
            "channels": channels,
            "channels_count": len(channels),
            "recent_activity": recent_activity,
            "monitoring_enabled": True,
            "check_interval": "30 minutes"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting monitoring details: {str(e)}")
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

@app.post("/reports/test")
async def test_daily_report():
    """Test daily report generation with debug info."""
    try:
        logger.info("🧪 Testing daily report generation...")
        
        # Check webhook configuration
        webhook_url = os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
        if not webhook_url:
            return {
                "success": False, 
                "error": "DISCORD_DAILY_REPORT_WEBHOOK not configured",
                "debug": "Add the webhook URL to environment variables"
            }
        
        # Test database connectivity
        supabase = get_supabase_client()
        db_status = "connected" if supabase else "not_connected"
        
        # Get data for testing
        summaries = []
        debug_info = {"webhook_configured": True, "database_status": db_status}
        
        if supabase:
            try:
                # Check what tables exist
                tables_to_check = ['summaries', 'transcripts']
                for table_name in tables_to_check:
                    try:
                        response = supabase.table(table_name).select('*').limit(5).execute()
                        debug_info[f"{table_name}_table"] = f"exists ({len(response.data or [])} records)"
                        if table_name == 'summaries' and response.data:
                            summaries = response.data[:3]  # Use a few for testing
                    except Exception as e:
                        debug_info[f"{table_name}_table"] = f"error: {str(e)}"
            except Exception as e:
                debug_info["database_error"] = str(e)
        
        # Generate test report
        if summaries:
            report = await generate_daily_report(summaries)
            if report:
                # Send test report
                test_message = f"🧪 **TEST Daily Report**\n\n{report}\n\n---\n*This is a test message*"
                await send_discord_message(webhook_url, test_message)
                return {
                    "success": True, 
                    "message": f"Test daily report sent with {len(summaries)} summaries",
                    "debug": debug_info
                }
            else:
                return {
                    "success": False,
                    "error": "Report generation failed",
                    "debug": debug_info
                }
        else:
            # Send test "no videos" message
            test_message = f"🧪 **TEST Daily Report - {datetime.now().strftime('%Y-%m-%d')}**\n\n📭 No videos found for testing.\n\n---\n*This is a test message*"
            await send_discord_message(webhook_url, test_message)
            return {
                "success": True,
                "message": "Test 'no videos' daily report sent",
                "debug": debug_info
            }
        
    except Exception as e:
        logger.error(f"❌ Error testing daily report: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/summaries")
async def get_summaries():
    """Get recent summaries from the database."""
    try:
        supabase = get_supabase_client()
        summaries = []
        
        if supabase:
            try:
                # Get summaries from last 30 days
                from datetime import datetime, timedelta
                thirty_days_ago = datetime.now() - timedelta(days=30)
                response = supabase.table('summaries').select('*').gte('created_at', thirty_days_ago.isoformat()).order('created_at', desc=True).limit(50).execute()
                summaries = response.data
            except Exception as e:
                logger.warning(f"Supabase query failed: {e}")
        
        if not summaries:
            # Fallback to local data
            try:
                import os
                summaries_file = os.path.join(os.path.dirname(__file__), 'shared', 'data', 'summaries.json')
                if os.path.exists(summaries_file):
                    with open(summaries_file, 'r') as f:
                        local_data = json.load(f)
                        summaries = local_data.get('summaries', [])[-50:]  # Last 50
            except Exception as e:
                logger.warning(f"Local summaries fallback failed: {e}")
        
        return {
            "success": True,
            "summaries": summaries,
            "count": len(summaries)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
async def get_analytics():
    """Get analytics data for the dashboard."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return {"success": False, "error": "Database not available"}
        
        # Get summary statistics
        summaries_result = supabase.table('summaries').select('*').execute()
        summaries = summaries_result.data
        
        # Get transcript statistics
        transcripts_result = supabase.table('transcripts').select('*').execute()
        transcripts = transcripts_result.data
        
        # Calculate analytics
        total_summaries = len(summaries)
        total_transcripts = len(transcripts)
        
        # Channel distribution
        channel_stats = {}
        for summary in summaries:
            channel = summary.get('channel', 'Unknown')
            channel_stats[channel] = channel_stats.get(channel, 0) + 1
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        week_ago_str = week_ago.isoformat()
        
        recent_summaries = [s for s in summaries if s.get('created_at', '') > week_ago_str]
        
        # Daily activity for the last 7 days
        daily_activity = {}
        for i in range(7):
            date = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_activity[date] = 0
        
        for summary in recent_summaries:
            if summary.get('created_at'):
                date = summary['created_at'][:10]  # Get YYYY-MM-DD part
                if date in daily_activity:
                    daily_activity[date] += 1
        
        # Top channels by content
        top_channels = sorted(channel_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Processing stats
        avg_summary_length = 0
        if summaries:
            total_length = sum(len(s.get('summary_text', '')) for s in summaries)
            avg_summary_length = total_length / len(summaries)
        
        # Get tracked channels count
        config = ConfigService()
        tracked_channels = config.load_config().get('tracked_channels', {})
        
        return {
            "success": True,
            "analytics": {
                "overview": {
                    "total_summaries": total_summaries,
                    "total_transcripts": total_transcripts,
                    "tracked_channels": len(tracked_channels),
                    "avg_summary_length": round(avg_summary_length, 2)
                },
                "recent_activity": {
                    "last_7_days": len(recent_summaries),
                    "daily_breakdown": daily_activity
                },
                "channel_distribution": dict(top_channels),
                "processing_stats": {
                    "total_processed": total_summaries,
                    "success_rate": 100,  # Assume all stored summaries were successful
                    "avg_processing_time": "2-3 minutes"  # Estimated
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting analytics: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/analytics/recent")
async def get_recent_activity(days: int = 7):
    """Get recent activity for specified number of days."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return {"success": False, "error": "Database not available"}
        
        # Calculate date range
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        start_date_str = start_date.isoformat()
        
        # Get recent summaries
        result = supabase.table('summaries').select('*').gte('created_at', start_date_str).order('created_at', desc=True).execute()
        summaries = result.data
        
        # Group by date
        activity_by_date = {}
        for summary in summaries:
            if summary.get('created_at'):
                date = summary['created_at'][:10]  # Get YYYY-MM-DD part
                if date not in activity_by_date:
                    activity_by_date[date] = []
                activity_by_date[date].append({
                    "id": summary.get('id'),
                    "title": summary.get('title'),
                    "channel": summary.get('channel'),
                    "video_id": summary.get('video_id'),
                    "created_at": summary.get('created_at')
                })
        
        return {
            "success": True,
            "days": days,
            "total_items": len(summaries),
            "activity": activity_by_date
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting recent activity: {str(e)}")
        return {"success": False, "error": str(e)}
        config_status = {}
        
        # Check environment variables (don't expose actual values)
        env_vars = [
            "OPENAI_API_KEY",
            "SUPABASE_URL", 
            "SUPABASE_KEY",
            "DISCORD_UPLOADS_WEBHOOK",
            "DISCORD_TRANSCRIPTS_WEBHOOK",
            "DISCORD_SUMMARIES_WEBHOOK",
            "DISCORD_DAILY_REPORT_WEBHOOK"
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            config_status[var.lower().replace('_', '')] = "configured" if value else "not_set"
        
        return {
            "success": True,
            "config": config_status
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test")
async def test_discord():
    """Test Discord webhook connectivity."""
    try:
        webhook_url = os.getenv('DISCORD_SUMMARIES_WEBHOOK')
        
        if not webhook_url:
            return {"success": False, "error": "No Discord webhook configured"}
        
        # Send test message
        test_message = "🧪 **Test Message from YouTube Summary Bot**\n\nIf you see this, the webhook is working correctly!"
        
        await send_discord_message(webhook_url, test_message)
        
        return {"success": True, "message": "Test message sent to Discord"}
        
    except Exception as e:
        logger.error(f"❌ Error testing Discord: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/discord/commands")
async def discord_commands_webhook(request: Request):
    """Handle Discord application commands webhook."""
    if not DISCORD_COMMANDS_ENABLED:
        raise HTTPException(status_code=503, detail="Discord commands not available")
    
    try:
        # Get headers for signature verification
        signature = request.headers.get('x-signature-ed25519')
        timestamp = request.headers.get('x-signature-timestamp')
        
        if not signature or not timestamp:
            raise HTTPException(status_code=401, detail="Missing signature headers")
        
        # Get request body
        body = await request.body()
        
        # Verify Discord signature
        if not await discord_handler.verify_discord_request(body, signature, timestamp):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse interaction
        interaction = await request.json()
        
        # Handle ping (Discord verification)
        if interaction.get('type') == 1:  # PING
            return {"type": 1}  # PONG
        
        # Handle application command
        if interaction.get('type') == 2:  # APPLICATION_COMMAND
            response = await discord_handler.handle_command(interaction)
            return response
        
        # Handle other interaction types
        return {
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {
                "content": "Interaction type not supported yet",
                "flags": 64  # EPHEMERAL
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Discord commands error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Analytics Endpoints
@app.get("/analytics/overview")
async def analytics_overview():
    """Get analytics overview with summary statistics."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Get total summaries count
        summaries_response = supabase.table('summaries').select('id', count='exact').execute()
        total_summaries = summaries_response.count if summaries_response.count else 0
        
        # Get tracked channels count
        channels_response = supabase.table('tracked_channels').select('id', count='exact').execute()
        tracked_channels_count = channels_response.count if channels_response.count else 0
        
        # Get recent activity (last 7 days)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent_response = supabase.table('summaries').select('id', count='exact').gte('created_at', seven_days_ago).execute()
        recent_summaries = recent_response.count if recent_response.count else 0
        
        # Get daily breakdown for last 7 days
        daily_counts = []
        for i in range(7):
            date = datetime.now(timezone.utc) - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            
            day_response = supabase.table('summaries').select('id', count='exact').gte('created_at', day_start).lte('created_at', day_end).execute()
            daily_counts.append({
                "date": date.strftime("%Y-%m-%d"),
                "count": day_response.count if day_response.count else 0
            })
        
        return {
            "success": True,
            "data": {
                "total_summaries": total_summaries,
                "tracked_channels": tracked_channels_count,
                "recent_summaries": recent_summaries,
                "daily_activity": daily_counts
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting analytics overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/recent")
async def analytics_recent():
    """Get recent activity analytics."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Get recent summaries with video metadata
        recent_response = supabase.table('summaries').select('*').order('created_at', desc=True).limit(20).execute()
        recent_summaries = recent_response.data if recent_response.data else []
        
        # Get processing statistics
        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        last_24h_response = supabase.table('summaries').select('id', count='exact').gte('created_at', twenty_four_hours_ago).execute()
        last_24h_count = last_24h_response.count if last_24h_response.count else 0
        
        return {
            "success": True,
            "data": {
                "recent_summaries": recent_summaries,
                "last_24h_count": last_24h_count,
                "total_tracked": len(recent_summaries)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting recent analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
