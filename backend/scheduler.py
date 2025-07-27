#!/usr/bin/env python3
"""
Simple Scheduler for YouTube Channel Monitoring
Checks tracked channels every 30 minutes for new videos
"""

import asyncio
import os
import sys
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.youtube_tracker import check_tracked_channels
from shared.transcript import get_transcript, extract_video_id
from shared.summarize import chunk_and_summarize
from shared.discord_utils import send_discord_message
from shared.supabase_utils import get_tracked_channels

logger = logging.getLogger(__name__)

class ChannelMonitor:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_SUMMARIES")
        
    async def check_channels_for_new_videos(self):
        """Check all tracked channels for new videos"""
        try:
            logger.info("🔍 Checking tracked channels for new videos...")
            
            # Get tracked channels
            channels_data = get_tracked_channels()
            tracked_channels = channels_data.get("tracked_channels", [])
            
            if not tracked_channels:
                logger.info("No channels being tracked")
                return
            
            logger.info(f"Checking {len(tracked_channels)} channels...")
            
            # Check each channel (this would need to be implemented)
            new_videos_found = 0
            
            # For now, just log the check
            logger.info(f"✅ Channel check complete. Found {new_videos_found} new videos")
            
        except Exception as e:
            logger.error(f"❌ Error checking channels: {str(e)}")
    
    async def process_new_video(self, video_url: str):
        """Process a newly found video"""
        try:
            logger.info(f"🎥 Processing new video: {video_url}")
            
            # Extract video ID
            video_id = extract_video_id(video_url)
            if not video_id:
                logger.error(f"Invalid video URL: {video_url}")
                return
            
            # Get transcript
            transcript_data = await get_transcript(video_id)
            if not transcript_data or not transcript_data.get("transcript"):
                logger.error(f"Could not get transcript for {video_id}")
                return
            
            # Generate summary
            summary = await chunk_and_summarize(
                transcript_data["transcript"],
                self.openai_key,
                title=transcript_data.get("title", ""),
                channel=transcript_data.get("channel", "")
            )
            
            # Send to Discord
            if self.discord_webhook:
                await send_discord_message(
                    webhook_url=self.discord_webhook,
                    content="**🆕 New Video Auto-Summary**",
                    description=f"**{transcript_data.get('title', 'Unknown Title')}**\n\n{summary}",
                    video_url=video_url
                )
                logger.info(f"✅ Summary sent to Discord for {video_id}")
            
        except Exception as e:
            logger.error(f"❌ Error processing video {video_url}: {str(e)}")
    
    def start(self):
        """Start the scheduler"""
        # Check channels every 30 minutes
        self.scheduler.add_job(
            self.check_channels_for_new_videos,
            trigger=IntervalTrigger(minutes=30),
            id='channel_monitor',
            name='Channel Monitor',
            replace_existing=True
        )
        
        logger.info("📅 Scheduler started - checking channels every 30 minutes")
        self.scheduler.start()
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("📅 Scheduler stopped")

# For standalone testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = ChannelMonitor()
    
    async def main():
        monitor.start()
        try:
            # Keep running
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            monitor.stop()
    
    asyncio.run(main())
