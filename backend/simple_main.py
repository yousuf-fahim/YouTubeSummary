#!/usr/bin/env python3
"""
Simplified YouTube Summary Bot Backend
A clean, focused FastAPI server for YouTube video processing
"""

import os
import sys
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging

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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="YouTube Summary Bot",
    description="Simple API for YouTube video processing and Discord integration",
    version="2.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/api/process-video")
async def process_video(request: VideoProcessRequest):
    """
    Process a YouTube video: extract transcript, generate summary, send to Discord
    """
    try:
        logger.info(f"Processing video: {request.youtube_url}")
        
        # Extract video ID
        video_id = extract_video_id(request.youtube_url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        # Get transcript
        logger.info(f"Getting transcript for video {video_id}")
        transcript_data = await get_transcript(video_id)
        
        if not transcript_data or not transcript_data.get("transcript"):
            raise HTTPException(status_code=404, detail="Could not get transcript for this video")
        
        # Generate summary
        logger.info(f"Generating summary for video {video_id}")
        summary = await chunk_and_summarize(
            transcript_data["transcript"],
            OPENAI_API_KEY,
            title=transcript_data.get("title", ""),
            channel=transcript_data.get("channel", "")
        )
        
        # Send to Discord if configured
        if DISCORD_WEBHOOK_SUMMARIES:
            logger.info(f"Sending summary to Discord for video {video_id}")
            await send_discord_message(
                webhook_url=DISCORD_WEBHOOK_SUMMARIES,
                content=f"**New Video Summary**",
                description=f"**{transcript_data.get('title', 'Unknown Title')}**\n\n{summary}",
                video_url=request.youtube_url
            )
        
        return {
            "status": "success",
            "video_id": video_id,
            "title": transcript_data.get("title"),
            "channel": transcript_data.get("channel"),
            "summary": summary,
            "discord_sent": bool(DISCORD_WEBHOOK_SUMMARIES)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/api/channels")
async def get_channels():
    """Get all tracked channels"""
    try:
        channels = await get_tracked_channels()
        return {
            "status": "success",
            "channels": channels,
            "count": len(channels)
        }
    except Exception as e:
        logger.error(f"Error getting channels: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/channels")
async def add_channel(request: ChannelRequest):
    """Add a channel to tracking"""
    try:
        await save_tracked_channel(request.channel_id, request.channel_name)
        return {
            "status": "success",
            "message": f"Channel {request.channel_id} added to tracking"
        }
    except Exception as e:
        logger.error(f"Error adding channel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/channels/{channel_id}")
async def remove_channel(channel_id: str):
    """Remove a channel from tracking"""
    try:
        await delete_tracked_channel(channel_id)
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
        summaries = await get_all_summaries()
        return {
            "status": "success",
            "summaries": summaries,
            "count": len(summaries)
        }
    except Exception as e:
        logger.error(f"Error getting summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Simple startup for Heroku
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
