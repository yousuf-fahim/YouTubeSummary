"""
Discord command webhook handler for YouTube Summary Bot
Handles Discord slash commands and bot interactions
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import HTTPException
import aiohttp
from shared.transcript import get_transcript, TranscriptError
from shared.summarize import generate_summary
from shared.supabase_utils import get_client
from shared.discord_utils import send_discord_message

logger = logging.getLogger(__name__)

class DiscordCommandHandler:
    def __init__(self):
        self.bot_token = os.getenv('DISCORD_BOT_TOKEN')
        self.application_id = os.getenv('DISCORD_APPLICATION_ID')
        self.public_key = os.getenv('DISCORD_PUBLIC_KEY')
    
    async def verify_discord_request(self, body: bytes, signature: str, timestamp: str) -> bool:
        """Verify Discord webhook signature"""
        try:
            from nacl.signing import VerifyKey
            from nacl.exceptions import BadSignatureError
            
            verify_key = VerifyKey(bytes.fromhex(self.public_key))
            verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
            return True
        except (BadSignatureError, Exception) as e:
            logger.error(f"Discord signature verification failed: {e}")
            return False
    
    async def handle_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Discord application command"""
        command_name = interaction.get('data', {}).get('name')
        
        if command_name == 'summarize':
            return await self.handle_summarize_command(interaction)
        elif command_name == 'status':
            return await self.handle_status_command(interaction)
        elif command_name == 'recent':
            return await self.handle_recent_command(interaction)
        elif command_name == 'help':
            return await self.handle_help_command(interaction)
        else:
            return {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "content": f"Unknown command: {command_name}"
                }
            }
    
    async def handle_summarize_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle /summarize [url] command"""
        try:
            options = interaction.get('data', {}).get('options', [])
            url = None
            
            for option in options:
                if option.get('name') == 'url':
                    url = option.get('value')
                    break
            
            if not url:
                return {
                    "type": 4,
                    "data": {
                        "content": "❌ Please provide a YouTube URL",
                        "flags": 64  # EPHEMERAL
                    }
                }
            
            # Respond immediately
            response = {
                "type": 4,
                "data": {
                    "content": f"🔄 Processing video: {url}\nThis may take a few minutes...",
                    "flags": 64  # EPHEMERAL
                }
            }
            
            # Process video asynchronously
            asyncio.create_task(self.process_video_for_discord(url, interaction))
            
            return response
            
        except Exception as e:
            logger.error(f"Error in summarize command: {e}")
            return {
                "type": 4,
                "data": {
                    "content": f"❌ Error processing command: {str(e)}",
                    "flags": 64
                }
            }
    
    async def handle_status_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle /status command"""
        try:
            # Get system status
            supabase = get_client()
            summaries_count = 0
            channels_count = 0
            
            if supabase:
                try:
                    summaries_result = supabase.table('summaries').select('id').execute()
                    summaries_count = len(summaries_result.data)
                    
                    # Get tracked channels from config
                    from shared.config_service import load_config
                    config = load_config()
                    channels_count = len(config.get('tracked_channels', {}))
                except Exception as e:
                    logger.error(f"Error getting status data: {e}")
            
            embed = {
                "title": "🤖 YouTube Summary Bot Status",
                "color": 0x00ff00,  # Green
                "fields": [
                    {
                        "name": "📊 Database",
                        "value": f"✅ Connected\n📝 {summaries_count} summaries",
                        "inline": True
                    },
                    {
                        "name": "📺 Monitoring",
                        "value": f"👀 {channels_count} channels tracked\n⏰ Running every 30 minutes",
                        "inline": True
                    },
                    {
                        "name": "📈 Daily Reports",
                        "value": "🕰️ Scheduled at 18:00 CEST\n✅ Active",
                        "inline": True
                    }
                ],
                "timestamp": "2025-07-30T00:00:00.000Z",
                "footer": {
                    "text": "YouTube Summary Bot"
                }
            }
            
            return {
                "type": 4,
                "data": {
                    "embeds": [embed]
                }
            }
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            return {
                "type": 4,
                "data": {
                    "content": f"❌ Error getting status: {str(e)}",
                    "flags": 64
                }
            }
    
    async def handle_recent_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle /recent command"""
        try:
            supabase = get_client()
            if not supabase:
                return {
                    "type": 4,
                    "data": {
                        "content": "❌ Database not available",
                        "flags": 64
                    }
                }
            
            # Get recent summaries
            result = supabase.table('summaries').select('*').order('created_at', desc=True).limit(5).execute()
            
            if not result.data:
                return {
                    "type": 4,
                    "data": {
                        "content": "📭 No recent summaries found"
                    }
                }
            
            embed = {
                "title": "📚 Recent Summaries",
                "color": 0x0099ff,  # Blue
                "fields": []
            }
            
            for summary in result.data:
                field_value = f"**Channel:** {summary.get('channel', 'Unknown')}\n"
                field_value += f"**Created:** {summary.get('created_at', '')[:10]}\n"
                if summary.get('summary_text'):
                    preview = summary['summary_text'][:100] + "..." if len(summary['summary_text']) > 100 else summary['summary_text']
                    field_value += f"**Preview:** {preview}"
                
                embed["fields"].append({
                    "name": f"🎥 {summary.get('title', 'Unknown Title')[:100]}",
                    "value": field_value,
                    "inline": False
                })
            
            return {
                "type": 4,
                "data": {
                    "embeds": [embed]
                }
            }
            
        except Exception as e:
            logger.error(f"Error in recent command: {e}")
            return {
                "type": 4,
                "data": {
                    "content": f"❌ Error getting recent summaries: {str(e)}",
                    "flags": 64
                }
            }
    
    async def handle_help_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle /help command"""
        embed = {
            "title": "🤖 YouTube Summary Bot Commands",
            "description": "Available commands for the YouTube Summary Bot",
            "color": 0x9932cc,  # Purple
            "fields": [
                {
                    "name": "📝 /summarize [url]",
                    "value": "Generate a summary for a YouTube video\nExample: `/summarize https://www.youtube.com/watch?v=dQw4w9WgXcQ`",
                    "inline": False
                },
                {
                    "name": "📊 /status",
                    "value": "Check bot status, database info, and monitoring status",
                    "inline": False
                },
                {
                    "name": "📚 /recent",
                    "value": "Show the 5 most recent video summaries",
                    "inline": False
                },
                {
                    "name": "❓ /help",
                    "value": "Show this help message",
                    "inline": False
                }
            ],
            "footer": {
                "text": "YouTube Summary Bot - AI-powered video summarization"
            }
        }
        
        return {
            "type": 4,
            "data": {
                "embeds": [embed]
            }
        }
    
    async def process_video_for_discord(self, url: str, interaction: Dict[str, Any]):
        """Process video and send result to Discord"""
        try:
            # Extract video ID
            from shared.transcript import extract_video_id
            video_id = extract_video_id(url)
            
            if not video_id:
                await self.send_followup_message(interaction, "❌ Invalid YouTube URL")
                return
            
            # Get transcript
            try:
                transcript_data = await get_transcript(video_id)
                transcript_text = transcript_data.get('transcript', '')
                title = transcript_data.get('title', 'Unknown Title')
                channel = transcript_data.get('channel', 'Unknown Channel')
            except TranscriptError as e:
                await self.send_followup_message(interaction, f"❌ Could not get transcript: {str(e)}")
                return
            
            # Generate summary
            try:
                summary_result = await generate_summary(transcript_text, title)
                summary_text = summary_result.get('summary', 'Could not generate summary')
            except Exception as e:
                logger.error(f"Error generating summary: {e}")
                await self.send_followup_message(interaction, f"❌ Could not generate summary: {str(e)}")
                return
            
            # Save to database
            try:
                supabase = get_client()
                if supabase:
                    supabase.table('summaries').insert({
                        'video_id': video_id,
                        'title': title,
                        'channel': channel,
                        'summary_text': summary_text,
                        'video_url': url
                    }).execute()
            except Exception as e:
                logger.error(f"Error saving to database: {e}")
            
            # Send summary to Discord
            embed = {
                "title": f"📝 Summary: {title[:100]}",
                "description": summary_text[:2000],  # Discord embed description limit
                "url": url,
                "color": 0x00ff00,  # Green
                "fields": [
                    {
                        "name": "📺 Channel",
                        "value": channel,
                        "inline": True
                    },
                    {
                        "name": "🎥 Video ID",
                        "value": video_id,
                        "inline": True
                    }
                ],
                "thumbnail": {
                    "url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                },
                "footer": {
                    "text": "YouTube Summary Bot"
                }
            }
            
            await self.send_followup_message(interaction, None, [embed])
            
        except Exception as e:
            logger.error(f"Error processing video for Discord: {e}")
            await self.send_followup_message(interaction, f"❌ Unexpected error: {str(e)}")
    
    async def send_followup_message(self, interaction: Dict[str, Any], content: Optional[str] = None, embeds: Optional[list] = None):
        """Send a followup message to Discord"""
        if not self.bot_token:
            logger.error("Discord bot token not configured")
            return
            
        try:
            followup_url = f"https://discord.com/api/v10/webhooks/{self.application_id}/{interaction['token']}"
            
            data = {}
            if content:
                data["content"] = content
            if embeds:
                data["embeds"] = embeds
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    followup_url,
                    json=data,
                    headers={"Authorization": f"Bot {self.bot_token}"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send followup message: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error sending followup message: {e}")

# Global handler instance
discord_handler = DiscordCommandHandler()
