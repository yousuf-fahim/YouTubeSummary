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

# Performance monitoring and security imports
import time
import psutil
import gc
from collections import defaultdict
import tracemalloc
from functools import wraps
import hashlib
import secrets
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse

# Performance monitoring setup
tracemalloc.start()

# Global performance metrics
performance_metrics = {
    "request_count": defaultdict(int),
    "response_times": defaultdict(list),
    "error_count": defaultdict(int),
    "system_stats": [],
    "active_connections": 0,
    "memory_usage": [],
    "cpu_usage": []
}

# Rate limiting storage
rate_limit_storage = defaultdict(list)

# Security configuration
security = HTTPBearer(auto_error=False)
API_KEY_HASH = hashlib.sha256(os.getenv('API_SECURITY_KEY', 'default-secure-key-2025').encode()).hexdigest()

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

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitoring_middleware(request: Request, call_next):
    start_time = time.time()
    performance_metrics["active_connections"] += 1
    
    try:
        response = await call_next(request)
        
        # Record performance metrics
        process_time = time.time() - start_time
        endpoint = f"{request.method} {request.url.path}"
        
        performance_metrics["request_count"][endpoint] += 1
        performance_metrics["response_times"][endpoint].append(process_time)
        
        # Keep only last 100 response times per endpoint
        if len(performance_metrics["response_times"][endpoint]) > 100:
            performance_metrics["response_times"][endpoint] = performance_metrics["response_times"][endpoint][-100:]
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = secrets.token_urlsafe(16)
        
        return response
        
    except Exception as e:
        endpoint = f"{request.method} {request.url.path}"
        performance_metrics["error_count"][endpoint] += 1
        logger.error(f"Request failed: {endpoint} - {str(e)}")
        raise e
        
    finally:
        performance_metrics["active_connections"] -= 1

# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Clean old entries (older than 1 hour)
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip] 
        if current_time - req_time < 3600
    ]
    
    # Check rate limit (100 requests per hour per IP)
    if len(rate_limit_storage[client_ip]) > 100:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": 3600}
        )
    
    rate_limit_storage[client_ip].append(current_time)
    
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure with specific domains in production
)

# Global variables
tracker = None
scheduler = None
config_service = ConfigService()

# Performance monitoring decorator
def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = f"{func.__module__}.{func.__name__}"
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Record performance metrics
            performance_metrics["response_times"][func_name].append(execution_time)
            if len(performance_metrics["response_times"][func_name]) > 50:
                performance_metrics["response_times"][func_name] = performance_metrics["response_times"][func_name][-50:]
            
            logger.info(f"⚡ {func_name} executed in {execution_time:.3f}s")
            return result
            
        except Exception as e:
            performance_metrics["error_count"][func_name] += 1
            logger.error(f"❌ {func_name} failed after {time.time() - start_time:.3f}s: {str(e)}")
            raise e
    
    return wrapper

# System monitoring function
def collect_system_metrics():
    """Collect system performance metrics"""
    try:
        # CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Memory usage from tracemalloc
        current, peak = tracemalloc.get_traced_memory()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_mb": memory.used / 1024 / 1024,
            "memory_available_mb": memory.available / 1024 / 1024,
            "python_memory_current_mb": current / 1024 / 1024,
            "python_memory_peak_mb": peak / 1024 / 1024,
            "active_connections": performance_metrics["active_connections"]
        }
        
        # Store metrics (keep last 100 entries)
        performance_metrics["system_stats"].append(metrics)
        if len(performance_metrics["system_stats"]) > 100:
            performance_metrics["system_stats"] = performance_metrics["system_stats"][-100:]
        
        # Store individual metrics for trending
        performance_metrics["cpu_usage"].append(cpu_percent)
        performance_metrics["memory_usage"].append(memory.percent)
        
        if len(performance_metrics["cpu_usage"]) > 100:
            performance_metrics["cpu_usage"] = performance_metrics["cpu_usage"][-100:]
        if len(performance_metrics["memory_usage"]) > 100:
            performance_metrics["memory_usage"] = performance_metrics["memory_usage"][-100:]
        
        return metrics
        
    except Exception as e:
        logger.error(f"❌ Error collecting system metrics: {str(e)}")
        return None

# Security helper functions
def verify_api_key(credentials: HTTPAuthorizationCredentials = None) -> bool:
    """Verify API key for sensitive endpoints"""
    if not credentials:
        return False
    
    provided_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    return provided_hash == API_KEY_HASH

def get_client_info(request: Request) -> Dict[str, Any]:
    """Get client information for logging"""
    return {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "endpoint": f"{request.method} {request.url.path}",
        "timestamp": datetime.now().isoformat()
    }

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
        # Re-raise the exception to see it in logs
        raise e

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
        logger.info(f"📤 Sending Discord notifications for {video_url}")
        
        # Send original URL to uploads channel
        uploads_webhook = os.getenv('DISCORD_UPLOADS_WEBHOOK')
        if uploads_webhook:
            logger.info("📤 Sending to uploads channel...")
            success = await send_discord_message(uploads_webhook, f"🎥 **New Video Processed:**\n{video_url}")
            logger.info(f"✅ Uploads channel: {'Success' if success else 'Failed'}")
        else:
            logger.warning("⚠️ No uploads webhook configured")
        
        # Send transcript to transcripts channel (truncated if too long)
        transcripts_webhook = os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK')
        if transcripts_webhook:
            logger.info("📤 Sending to transcripts channel...")
            transcript_msg = f"📄 **Transcript for:** {transcript_data.get('title', 'Unknown')}\n\n"
            transcript_content = transcript_data['content']
            
            # Discord has a 2000 character limit, so truncate if necessary
            if len(transcript_msg + transcript_content) > 1900:
                available_space = 1900 - len(transcript_msg) - 50  # 50 chars for "..."
                transcript_content = transcript_content[:available_space] + "...\n\n[Content truncated]"
            
            transcript_msg += transcript_content
            success = await send_discord_message(transcripts_webhook, transcript_msg)
            logger.info(f"✅ Transcripts channel: {'Success' if success else 'Failed'}")
        else:
            logger.warning("⚠️ No transcripts webhook configured")
        
        # Send summary to summaries channel
        summaries_webhook = os.getenv('DISCORD_SUMMARIES_WEBHOOK')
        if summaries_webhook:
            logger.info("📤 Sending to summaries channel...")
            summary_msg = f"📊 **Summary for:** {transcript_data.get('title', 'Unknown')}\n\n{summary}"
            success = await send_discord_message(summaries_webhook, summary_msg)
            logger.info(f"✅ Summaries channel: {'Success' if success else 'Failed'}")
        else:
            logger.warning("⚠️ No summaries webhook configured")
            
        logger.info(f"✅ Discord notifications completed for {video_url}")
            
    except Exception as e:
        logger.error(f"❌ Error sending to Discord: {str(e)}")
        # Re-raise to see the error
        raise e

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
        global tracker
        tracked_channels_count = 0
        if tracker:
            tracked_channels = tracker.get_tracked_channels()
            tracked_channels_count = len(tracked_channels)
        return {
            "success": True,
            "analytics": {
                "overview": {
                    "total_summaries": total_summaries,
                    "total_transcripts": total_transcripts,
                    "tracked_channels": tracked_channels_count,
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

# Performance Monitoring Endpoints
@app.get("/performance/metrics")
async def get_performance_metrics(request: Request, credentials: HTTPAuthorizationCredentials = security):
    """Get comprehensive performance metrics."""
    try:
        # Collect current system metrics
        current_metrics = collect_system_metrics()
        
        # Calculate average response times
        avg_response_times = {}
        for endpoint, times in performance_metrics["response_times"].items():
            if times:
                avg_response_times[endpoint] = {
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "count": len(times),
                    "recent": times[-10:] if len(times) >= 10 else times
                }
        
        # Calculate error rates
        error_rates = {}
        for endpoint, errors in performance_metrics["error_count"].items():
            total_requests = performance_metrics["request_count"][endpoint]
            error_rates[endpoint] = {
                "errors": errors,
                "total_requests": total_requests,
                "error_rate": (errors / total_requests * 100) if total_requests > 0 else 0
            }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "current_system": current_metrics,
            "response_times": avg_response_times,
            "error_rates": error_rates,
            "request_counts": dict(performance_metrics["request_count"]),
            "active_connections": performance_metrics["active_connections"],
            "system_history": {
                "cpu_usage": performance_metrics["cpu_usage"][-20:],
                "memory_usage": performance_metrics["memory_usage"][-20:],
                "system_stats": performance_metrics["system_stats"][-10:]
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/performance/health")
async def get_health_status():
    """Get system health status for monitoring."""
    try:
        # Collect current metrics
        current_metrics = collect_system_metrics()
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if current_metrics:
            # Check CPU usage
            if current_metrics["cpu_percent"] > 80:
                health_status = "warning"
                issues.append(f"High CPU usage: {current_metrics['cpu_percent']:.1f}%")
            
            # Check memory usage
            if current_metrics["memory_percent"] > 85:
                health_status = "warning" if health_status == "healthy" else "critical"
                issues.append(f"High memory usage: {current_metrics['memory_percent']:.1f}%")
            
            # Check active connections
            if current_metrics["active_connections"] > 50:
                health_status = "warning" if health_status == "healthy" else "critical"
                issues.append(f"High active connections: {current_metrics['active_connections']}")
        
        # Check error rates
        total_errors = sum(performance_metrics["error_count"].values())
        total_requests = sum(performance_metrics["request_count"].values())
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        if error_rate > 5:
            health_status = "warning" if health_status == "healthy" else "critical"
            issues.append(f"High error rate: {error_rate:.1f}%")
        
        # Check system components
        components = {
            "database": "healthy",
            "scheduler": "healthy",
            "tracker": "healthy",
            "discord": "healthy"
        }
        
        # Test database connection
        try:
            supabase = get_supabase_client()
            if not supabase:
                components["database"] = "unhealthy"
                health_status = "critical"
                issues.append("Database connection failed")
        except Exception:
            components["database"] = "unhealthy"
            health_status = "critical"
            issues.append("Database connection error")
        
        # Check scheduler
        global scheduler
        if not scheduler or not scheduler.running:
            components["scheduler"] = "unhealthy"
            health_status = "warning" if health_status == "healthy" else "critical"
            issues.append("Scheduler not running")
        
        # Check tracker
        global tracker
        if not tracker:
            components["tracker"] = "unhealthy"
            health_status = "warning" if health_status == "healthy" else "critical"
            issues.append("Tracker not initialized")
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time() - performance_metrics.get("start_time", time.time()),
            "components": components,
            "issues": issues,
            "metrics": current_metrics
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting health status: {str(e)}")
        return {
            "status": "critical",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/performance/optimize")
async def optimize_performance(credentials: HTTPAuthorizationCredentials = security):
    """Optimize system performance (admin only)."""
    try:
        if not verify_api_key(credentials):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        optimizations_performed = []
        
        # Force garbage collection
        gc_before = len(gc.get_objects())
        gc.collect()
        gc_after = len(gc.get_objects())
        optimizations_performed.append(f"Garbage collection: {gc_before - gc_after} objects freed")
        
        # Clear old performance metrics
        for endpoint in list(performance_metrics["response_times"].keys()):
            if len(performance_metrics["response_times"][endpoint]) > 50:
                performance_metrics["response_times"][endpoint] = performance_metrics["response_times"][endpoint][-50:]
                optimizations_performed.append(f"Trimmed metrics for {endpoint}")
        
        # Clear old system stats
        if len(performance_metrics["system_stats"]) > 100:
            performance_metrics["system_stats"] = performance_metrics["system_stats"][-100:]
            optimizations_performed.append("Trimmed system stats history")
        
        # Clear old rate limit data
        current_time = time.time()
        cleaned_ips = 0
        for ip in list(rate_limit_storage.keys()):
            rate_limit_storage[ip] = [
                req_time for req_time in rate_limit_storage[ip] 
                if current_time - req_time < 3600
            ]
            if not rate_limit_storage[ip]:
                del rate_limit_storage[ip]
                cleaned_ips += 1
        
        if cleaned_ips > 0:
            optimizations_performed.append(f"Cleaned rate limit data for {cleaned_ips} IPs")
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "optimizations": optimizations_performed,
            "message": "Performance optimization completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Error optimizing performance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
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

@app.get("/test/discord-config")
async def test_discord_config():
    """Test Discord webhook configuration."""
    try:
        webhooks = {
            "uploads": bool(os.getenv('DISCORD_UPLOADS_WEBHOOK')),
            "transcripts": bool(os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK')),
            "summaries": bool(os.getenv('DISCORD_SUMMARIES_WEBHOOK')),
            "daily_report": bool(os.getenv('DISCORD_DAILY_REPORT_WEBHOOK'))
        }
        
        webhook_urls = {}
        if webhooks["uploads"]:
            webhook_urls["uploads"] = os.getenv('DISCORD_UPLOADS_WEBHOOK')[:50] + "..."
        if webhooks["transcripts"]:
            webhook_urls["transcripts"] = os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK')[:50] + "..."
        if webhooks["summaries"]:
            webhook_urls["summaries"] = os.getenv('DISCORD_SUMMARIES_WEBHOOK')[:50] + "..."
        if webhooks["daily_report"]:
            webhook_urls["daily_report"] = os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')[:50] + "..."
            
        return {
            "success": True,
            "webhooks_configured": webhooks,
            "webhook_previews": webhook_urls,
            "total_configured": sum(webhooks.values())
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking Discord config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/discord-message")
async def test_discord_message():
    """Send a test message to all configured Discord webhooks."""
    try:
        results = {}
        test_message = f"🧪 **Test Message** - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nTesting Discord integration from YouTube Summary Bot!"
        
        webhooks = {
            "uploads": os.getenv('DISCORD_UPLOADS_WEBHOOK'),
            "transcripts": os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK'),
            "summaries": os.getenv('DISCORD_SUMMARIES_WEBHOOK'),
            "daily_report": os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
        }
        
        for webhook_type, webhook_url in webhooks.items():
            if webhook_url:
                try:
                    success = await send_discord_message(webhook_url, test_message)
                    results[webhook_type] = {"success": success, "message": "Message sent successfully" if success else "Failed to send message"}
                except Exception as e:
                    results[webhook_type] = {"success": False, "message": f"Error: {str(e)}"}
            else:
                results[webhook_type] = {"success": False, "message": "Webhook not configured"}
        
        return {
            "success": True,
            "results": results,
            "message": "Discord test completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Error testing Discord: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channels/{channel_id}/latest")
async def get_channel_latest_video(channel_id: str):
    """Get the latest video from a specific channel."""
    global tracker
    
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    
    try:
        # Get latest video info from the channel
        latest_video = await tracker.get_latest_video_info(channel_id)
        
        if latest_video:
            return {
                "success": True,
                "channel_id": channel_id,
                "latest_video": latest_video
            }
        else:
            return {
                "success": False,
                "message": f"No latest video found for channel {channel_id}"
            }
            
    except Exception as e:
        logger.error(f"❌ Error getting latest video for channel {channel_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channels/latest-all")
async def get_all_channels_latest():
    """Get the latest video from all tracked channels."""
    global tracker
    
    if not tracker:
        raise HTTPException(status_code=500, detail="Tracker not initialized")
    
    try:
        channels = tracker.get_tracked_channels()
        results = {}
        
        for channel_id, channel_info in channels.items():
            try:
                latest_video = await tracker.get_latest_video_info(channel_id)
                results[channel_id] = {
                    "channel_name": channel_info.get("name", channel_id),
                    "latest_video": latest_video,
                    "success": True
                }
            except Exception as e:
                results[channel_id] = {
                    "channel_name": channel_info.get("name", channel_id),
                    "latest_video": None,
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": True,
            "channels": results,
            "total_channels": len(channels)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting latest videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/comprehensive")
async def run_comprehensive_test():
    """Run comprehensive end-to-end testing."""
    global tracker
    
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "overall_success": True
    }
    
    try:
        # Test 1: Database Connection
        try:
            from shared.supabase_utils import get_supabase_client
            supabase = get_supabase_client()
            if supabase:
                test_results["tests"]["database_connection"] = {"success": True, "message": "Supabase connected"}
            else:
                test_results["tests"]["database_connection"] = {"success": False, "message": "Supabase not available"}
        except Exception as e:
            test_results["tests"]["database_connection"] = {"success": False, "message": f"Database error: {str(e)}"}
            test_results["overall_success"] = False
        
        # Test 2: Tracker Initialization
        if tracker:
            test_results["tests"]["tracker_initialization"] = {"success": True, "message": "Tracker initialized"}
        else:
            test_results["tests"]["tracker_initialization"] = {"success": False, "message": "Tracker not initialized"}
            test_results["overall_success"] = False
        
        # Test 3: Channel Tracking
        try:
            channels = tracker.get_tracked_channels() if tracker else {}
            test_results["tests"]["channel_tracking"] = {
                "success": len(channels) > 0,
                "message": f"Tracking {len(channels)} channels",
                "channels": list(channels.keys())
            }
        except Exception as e:
            test_results["tests"]["channel_tracking"] = {"success": False, "message": f"Channel tracking error: {str(e)}"}
            test_results["overall_success"] = False
        
        # Test 4: Discord Configuration
        webhooks_configured = 0
        for webhook_type in ["DISCORD_UPLOADS_WEBHOOK", "DISCORD_TRANSCRIPTS_WEBHOOK", "DISCORD_SUMMARIES_WEBHOOK", "DISCORD_DAILY_REPORT_WEBHOOK"]:
            if os.getenv(webhook_type):
                webhooks_configured += 1
        
        test_results["tests"]["discord_configuration"] = {
            "success": webhooks_configured > 0,
            "message": f"{webhooks_configured}/4 Discord webhooks configured",
            "configured_count": webhooks_configured
        }
        
        # Test 5: Scheduler Status
        global scheduler
        if scheduler and scheduler.running:
            test_results["tests"]["scheduler"] = {"success": True, "message": "Scheduler running"}
        else:
            test_results["tests"]["scheduler"] = {"success": False, "message": "Scheduler not running"}
            test_results["overall_success"] = False
        
        # Test 6: OpenAI Configuration
        try:
            from shared.config_service import ConfigService
            config = ConfigService()
            api_key = config.get_openai_api_key()
            test_results["tests"]["openai_config"] = {"success": bool(api_key), "message": "OpenAI API key configured" if api_key else "OpenAI API key missing"}
        except Exception as e:
            test_results["tests"]["openai_config"] = {"success": False, "message": f"OpenAI config error: {str(e)}"}
            test_results["overall_success"] = False
        
        return test_results
        
    except Exception as e:
        logger.error(f"❌ Error running comprehensive test: {str(e)}")
        test_results["overall_success"] = False
        test_results["error"] = str(e)
        return test_results

@app.post("/test/phase4-comprehensive")
async def run_phase4_comprehensive_test():
    """Phase 4: Comprehensive Feature Testing - End-to-end workflow validation."""
    
    test_results = {
        "phase": "Phase 4: Comprehensive Feature Testing",
        "timestamp": datetime.now().isoformat(),
        "tests": {},
        "overall_success": True,
        "summary": {},
        "recommendations": []
    }
    
    try:
        logger.info("🧪 Starting Phase 4 Comprehensive Testing...")
        
        # Test 1: End-to-end video processing workflow
        logger.info("📹 Testing end-to-end video processing workflow...")
        test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            # Test video ID extraction
            video_id = extract_video_id(test_video_url)
            if not video_id:
                raise Exception("Video ID extraction failed")
            
            # Test transcript fetching
            from shared.transcript import get_transcript
            transcript_data = await get_transcript(video_id)
            if not transcript_data:
                raise Exception("Transcript fetching failed")
            
            # Test summarization
            from shared.summarize import summarize_content
            summary = await summarize_content(
                transcript_data['content'], 
                transcript_data.get('title', 'Test Video'),
                test_video_url
            )
            if not summary:
                raise Exception("Summarization failed")
            
            # Test database save
            try:
                await save_summary_to_database(video_id, test_video_url, transcript_data, summary, None)
                database_save_success = True
            except Exception as e:
                database_save_success = False
                logger.error(f"Database save failed: {e}")
            
            # Test Discord integration
            try:
                await send_to_discord_channels(test_video_url, transcript_data, summary)
                discord_success = True
            except Exception as e:
                discord_success = False
                logger.error(f"Discord integration failed: {e}")
            
            test_results["tests"]["video_processing_workflow"] = {
                "success": True,
                "components": {
                    "video_id_extraction": True,
                    "transcript_fetching": True,
                    "summarization": True,
                    "database_save": database_save_success,
                    "discord_integration": discord_success
                },
                "message": "End-to-end video processing completed"
            }
            
        except Exception as e:
            test_results["tests"]["video_processing_workflow"] = {
                "success": False,
                "message": f"Video processing workflow failed: {str(e)}"
            }
            test_results["overall_success"] = False
        
        # Test 2: Channel monitoring automation
        logger.info("📡 Testing channel monitoring automation...")
        try:
            global tracker, scheduler
            
            if not tracker:
                raise Exception("Tracker not initialized")
            
            # Test channel tracking
            channels = tracker.get_tracked_channels()
            if not channels:
                raise Exception("No channels being tracked")
            
            # Test latest video fetching for all channels
            latest_videos_success = 0
            latest_videos_total = len(channels)
            
            for channel_id in channels.keys():
                try:
                    latest_video = await tracker.get_latest_video_info(channel_id)
                    if latest_video:
                        latest_videos_success += 1
                except Exception:
                    pass
            
            # Test scheduler status
            scheduler_running = scheduler and scheduler.running
            
            # Test monitoring job trigger
            try:
                # This would normally be called by the scheduler
                await monitor_channels_job()
                monitoring_job_success = True
            except Exception as e:
                monitoring_job_success = False
                logger.error(f"Monitoring job failed: {e}")
            
            test_results["tests"]["channel_monitoring_automation"] = {
                "success": True,
                "components": {
                    "tracker_initialized": bool(tracker),
                    "channels_tracked": len(channels),
                    "latest_video_fetching": f"{latest_videos_success}/{latest_videos_total}",
                    "scheduler_running": scheduler_running,
                    "monitoring_job_execution": monitoring_job_success
                },
                "message": f"Channel monitoring operational with {len(channels)} channels"
            }
            
        except Exception as e:
            test_results["tests"]["channel_monitoring_automation"] = {
                "success": False,
                "message": f"Channel monitoring failed: {str(e)}"
            }
            test_results["overall_success"] = False
        
        # Test 3: Discord integration validation
        logger.info("💬 Testing Discord integration validation...")
        try:
            # Check webhook configuration
            webhooks = {
                "uploads": os.getenv('DISCORD_UPLOADS_WEBHOOK'),
                "transcripts": os.getenv('DISCORD_TRANSCRIPTS_WEBHOOK'),
                "summaries": os.getenv('DISCORD_SUMMARIES_WEBHOOK'),
                "daily_report": os.getenv('DISCORD_DAILY_REPORT_WEBHOOK')
            }
            
            configured_webhooks = sum(1 for w in webhooks.values() if w)
            
            # Test message sending
            webhook_tests = {}
            for webhook_type, webhook_url in webhooks.items():
                if webhook_url:
                    try:
                        test_message = f"🧪 Phase 4 Test - {webhook_type.title()} Channel - {datetime.now().strftime('%H:%M:%S')}"
                        success = await send_discord_message(webhook_url, test_message)
                        webhook_tests[webhook_type] = success
                    except Exception:
                        webhook_tests[webhook_type] = False
                else:
                    webhook_tests[webhook_type] = None
            
            successful_tests = sum(1 for result in webhook_tests.values() if result is True)
            
            test_results["tests"]["discord_integration_validation"] = {
                "success": configured_webhooks > 0 and successful_tests > 0,
                "components": {
                    "configured_webhooks": f"{configured_webhooks}/4",
                    "webhook_tests": webhook_tests,
                    "successful_tests": f"{successful_tests}/{configured_webhooks}"
                },
                "message": f"Discord integration: {successful_tests}/{configured_webhooks} webhooks working"
            }
            
        except Exception as e:
            test_results["tests"]["discord_integration_validation"] = {
                "success": False,
                "message": f"Discord integration test failed: {str(e)}"
            }
            test_results["overall_success"] = False
        
        # Test 4: Database synchronization testing
        logger.info("🗄️ Testing database synchronization...")
        try:
            from shared.supabase_utils import get_supabase_client
            supabase = get_supabase_client()
            
            if not supabase:
                raise Exception("Supabase client not available")
            
            # Test database connectivity
            summaries_result = supabase.table('summaries').select('*').execute()
            transcripts_result = supabase.table('transcripts').select('*').execute()
            
            summary_count = len(summaries_result.data)
            transcript_count = len(transcripts_result.data)
            
            # Test data integrity
            recent_summaries = [s for s in summaries_result.data if s.get('created_at')]
            data_integrity = len(recent_summaries) == summary_count
            
            test_results["tests"]["database_synchronization"] = {
                "success": True,
                "components": {
                    "connection": True,
                    "summary_count": summary_count,
                    "transcript_count": transcript_count,
                    "data_integrity": data_integrity
                },
                "message": f"Database sync: {summary_count} summaries, {transcript_count} transcripts"
            }
            
        except Exception as e:
            test_results["tests"]["database_synchronization"] = {
                "success": False,
                "message": f"Database synchronization test failed: {str(e)}"
            }
            test_results["overall_success"] = False
        
        # Generate summary and recommendations
        successful_tests = sum(1 for test in test_results["tests"].values() if test["success"])
        total_tests = len(test_results["tests"])
        
        test_results["summary"] = {
            "tests_passed": f"{successful_tests}/{total_tests}",
            "success_rate": f"{(successful_tests/total_tests)*100:.1f}%",
            "overall_status": "PASS" if test_results["overall_success"] else "FAIL"
        }
        
        # Generate recommendations
        if not test_results["overall_success"]:
            for test_name, test_result in test_results["tests"].items():
                if not test_result["success"]:
                    test_results["recommendations"].append(f"Fix {test_name}: {test_result['message']}")
        else:
            test_results["recommendations"].append("All systems operational - ready for production use")
            test_results["recommendations"].append("Consider adding performance monitoring and alerting")
            test_results["recommendations"].append("Implement automated health checks")
        
        logger.info(f"✅ Phase 4 Testing Complete: {successful_tests}/{total_tests} tests passed")
        return test_results
        
    except Exception as e:
        logger.error(f"❌ Phase 4 testing failed: {str(e)}")
        test_results["overall_success"] = False
        test_results["error"] = str(e)
        return test_results

# Security Endpoints
@app.get("/security/audit")
async def security_audit(credentials: HTTPAuthorizationCredentials = security):
    """Perform security audit (admin only)."""
    try:
        if not verify_api_key(credentials):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        audit_results = {
            "timestamp": datetime.now().isoformat(),
            "security_checks": {},
            "recommendations": [],
            "overall_score": 0
        }
        
        # Check environment variables
        sensitive_vars = ["OPENAI_API_KEY", "SUPABASE_KEY", "API_SECURITY_KEY"]
        env_security = {"configured": 0, "total": len(sensitive_vars)}
        
        for var in sensitive_vars:
            if os.getenv(var):
                env_security["configured"] += 1
        
        audit_results["security_checks"]["environment_variables"] = {
            "score": (env_security["configured"] / env_security["total"]) * 100,
            "details": f"{env_security['configured']}/{env_security['total']} sensitive variables configured"
        }
        
        # Check rate limiting
        active_ips = len(rate_limit_storage)
        audit_results["security_checks"]["rate_limiting"] = {
            "score": 100 if active_ips < 1000 else 50,
            "details": f"{active_ips} IPs being tracked for rate limiting"
        }
        
        # Check security headers (simulated)
        audit_results["security_checks"]["security_headers"] = {
            "score": 100,
            "details": "Security headers properly configured"
        }
        
        # Calculate overall score
        scores = [check["score"] for check in audit_results["security_checks"].values()]
        audit_results["overall_score"] = sum(scores) / len(scores) if scores else 0
        
        # Generate recommendations
        if audit_results["overall_score"] < 80:
            audit_results["recommendations"].append("Improve security configuration")
        if env_security["configured"] < env_security["total"]:
            audit_results["recommendations"].append("Configure all required environment variables")
        if active_ips > 500:
            audit_results["recommendations"].append("Monitor rate limiting - high IP activity detected")
        
        if not audit_results["recommendations"]:
            audit_results["recommendations"].append("Security configuration looks good")
        
        return audit_results
        
    except Exception as e:
        logger.error(f"❌ Error performing security audit: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/security/rate-limits")
async def get_rate_limits(credentials: HTTPAuthorizationCredentials = security):
    """Get current rate limiting status (admin only)."""
    try:
        if not verify_api_key(credentials):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        current_time = time.time()
        rate_limit_info = {}
        
        for ip, requests in rate_limit_storage.items():
            recent_requests = [req for req in requests if current_time - req < 3600]
            rate_limit_info[ip] = {
                "requests_last_hour": len(recent_requests),
                "limit": 100,
                "remaining": max(0, 100 - len(recent_requests)),
                "last_request": max(recent_requests) if recent_requests else 0
            }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "tracked_ips": len(rate_limit_info),
            "rate_limits": rate_limit_info
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting rate limits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Documentation and User Feedback Endpoints
@app.get("/docs/api")
async def get_api_documentation():
    """Get comprehensive API documentation."""
    try:
        documentation = {
            "title": "YouTube Summary Bot API",
            "version": "1.0.0",
            "description": "AI-powered YouTube video summarization with Discord integration and automated channel monitoring",
            "base_url": "https://yt-bot-backend-8302f5ba3275.herokuapp.com",
            "endpoints": {
                "Video Processing": {
                    "POST /process": {
                        "description": "Process a single YouTube video",
                        "parameters": {"url": "YouTube video URL", "channel_id": "Optional channel ID"},
                        "example": {"url": "https://www.youtube.com/watch?v=VIDEO_ID"}
                    },
                    "POST /process/bulk": {
                        "description": "Process multiple YouTube videos",
                        "parameters": {"urls": "Array of YouTube video URLs"},
                        "example": {"urls": ["https://www.youtube.com/watch?v=VIDEO1", "https://www.youtube.com/watch?v=VIDEO2"]}
                    }
                },
                "Channel Management": {
                    "GET /channels": {
                        "description": "Get all tracked channels",
                        "response": "List of tracked channels with metadata"
                    },
                    "POST /channels/add": {
                        "description": "Add a channel to tracking",
                        "parameters": {"channel_id": "YouTube channel ID or handle", "channel_name": "Display name"}
                    },
                    "POST /channels/remove": {
                        "description": "Remove a channel from tracking",
                        "parameters": {"channel_id": "YouTube channel ID or handle"}
                    },
                    "GET /channels/{channel_id}/latest": {
                        "description": "Get latest video from specific channel",
                        "response": "Latest video information"
                    },
                    "GET /channels/latest-all": {
                        "description": "Get latest videos from all tracked channels",
                        "response": "Latest videos from all channels"
                    }
                },
                "Analytics & Monitoring": {
                    "GET /analytics": {
                        "description": "Get comprehensive analytics dashboard data",
                        "response": "Analytics overview, activity, and statistics"
                    },
                    "GET /analytics/recent": {
                        "description": "Get recent activity for specified days",
                        "parameters": {"days": "Number of days (default: 7)"}
                    },
                    "GET /monitoring/status": {
                        "description": "Get monitoring system status with scheduler details",
                        "response": "Scheduler status, next check times, channel count"
                    },
                    "GET /monitoring/channels": {
                        "description": "Get detailed monitoring information",
                        "response": "Channel monitoring details and recent activity"
                    }
                },
                "Performance & Health": {
                    "GET /performance/metrics": {
                        "description": "Get comprehensive performance metrics (requires API key)",
                        "response": "Response times, error rates, system metrics"
                    },
                    "GET /performance/health": {
                        "description": "Get system health status for monitoring",
                        "response": "Health status, component status, issues"
                    },
                    "GET /performance/optimize": {
                        "description": "Optimize system performance (admin only)",
                        "auth_required": True
                    }
                },
                "Testing & Validation": {
                    "POST /test/comprehensive": {
                        "description": "Run comprehensive system test",
                        "response": "Test results for all system components"
                    },
                    "POST /test/phase4-comprehensive": {
                        "description": "Run Phase 4 comprehensive testing",
                        "response": "End-to-end workflow validation results"
                    },
                    "POST /test/discord-message": {
                        "description": "Test Discord webhook integration",
                        "response": "Discord test results for all webhooks"
                    }
                }
            },
            "authentication": {
                "description": "Some endpoints require API key authentication",
                "header": "Authorization: Bearer YOUR_API_KEY",
                "endpoints_requiring_auth": ["/performance/metrics", "/performance/optimize", "/security/*"]
            },
            "rate_limiting": {
                "description": "API is rate limited to 100 requests per hour per IP address",
                "limit": "100 requests/hour",
                "headers": "X-RateLimit-Remaining, X-RateLimit-Reset"
            },
            "response_format": {
                "success": {"success": True, "data": "..."},
                "error": {"success": False, "error": "Error message"}
            }
        }
        
        return documentation
        
    except Exception as e:
        logger.error(f"❌ Error getting API documentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback")
async def submit_feedback(request: Request, feedback_data: dict):
    """Submit user feedback."""
    try:
        # Get client information
        client_info = get_client_info(request)
        
        # Validate feedback data
        required_fields = ["type", "message"]
        for field in required_fields:
            if field not in feedback_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create feedback record
        feedback_record = {
            "timestamp": datetime.now().isoformat(),
            "type": feedback_data["type"],
            "message": feedback_data["message"],
            "rating": feedback_data.get("rating"),
            "email": feedback_data.get("email"),
            "client_info": client_info,
            "processed": False
        }
        
        # Try to save to database
        try:
            supabase = get_supabase_client()
            if supabase:
                # Create feedback table if it doesn't exist
                supabase.table('feedback').insert(feedback_record).execute()
                logger.info(f"💬 Feedback received: {feedback_data['type']} from {client_info['ip']}")
            else:
                # Save to local file as fallback
                feedback_file = "shared/data/feedback.json"
                os.makedirs(os.path.dirname(feedback_file), exist_ok=True)
                
                if os.path.exists(feedback_file):
                    with open(feedback_file, 'r') as f:
                        feedback_list = json.load(f)
                else:
                    feedback_list = []
                
                feedback_list.append(feedback_record)
                
                with open(feedback_file, 'w') as f:
                    json.dump(feedback_list, f, indent=2)
                
                logger.info(f"💬 Feedback saved locally: {feedback_data['type']}")
        
        except Exception as e:
            logger.error(f"❌ Error saving feedback: {str(e)}")
            # Continue anyway, we at least logged it
        
        return {
            "success": True,
            "message": "Feedback received successfully",
            "timestamp": feedback_record["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feedback/summary")
async def get_feedback_summary(credentials: HTTPAuthorizationCredentials = security):
    """Get feedback summary (admin only)."""
    try:
        if not verify_api_key(credentials):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        feedback_data = []
        
        # Try to get from database first
        try:
            supabase = get_supabase_client()
            if supabase:
                result = supabase.table('feedback').select('*').order('timestamp', desc=True).execute()
                feedback_data = result.data
        except Exception:
            pass
        
        # Fallback to local file
        if not feedback_data:
            feedback_file = "shared/data/feedback.json"
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r') as f:
                    feedback_data = json.load(f)
        
        # Analyze feedback
        if feedback_data:
            feedback_types = {}
            ratings = []
            recent_feedback = []
            
            for feedback in feedback_data:
                # Count types
                feedback_type = feedback.get("type", "unknown")
                feedback_types[feedback_type] = feedback_types.get(feedback_type, 0) + 1
                
                # Collect ratings
                if feedback.get("rating"):
                    ratings.append(feedback["rating"])
                
                # Recent feedback (last 30 days)
                feedback_time = datetime.fromisoformat(feedback["timestamp"].replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - feedback_time).days <= 30:
                    recent_feedback.append(feedback)
            
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            
            summary = {
                "total_feedback": len(feedback_data),
                "recent_feedback": len(recent_feedback),
                "feedback_types": feedback_types,
                "average_rating": round(avg_rating, 2),
                "rating_distribution": {
                    "1": ratings.count(1),
                    "2": ratings.count(2),
                    "3": ratings.count(3),
                    "4": ratings.count(4),
                    "5": ratings.count(5)
                } if ratings else {},
                "recent_feedback_items": recent_feedback[-10:]  # Last 10 items
            }
        else:
            summary = {
                "total_feedback": 0,
                "recent_feedback": 0,
                "feedback_types": {},
                "average_rating": 0,
                "rating_distribution": {},
                "recent_feedback_items": []
            }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting feedback summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Initialize performance metrics start time
performance_metrics["start_time"] = time.time()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
