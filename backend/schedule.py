import os
import json
import asyncio
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from shared.discord_utils import send_discord_message
from shared.summarize import generate_daily_report
from shared.youtube_tracker import check_tracked_channels
import logging
import pytz

def setup_scheduler():
    """
    Set up a scheduler for periodic tasks
    
    Returns:
        BackgroundScheduler: The configured scheduler (not started)
    """
    scheduler = BackgroundScheduler()
    
    # Configure timezone settings
    cest = pytz.timezone('Europe/Paris')
    
    # You can add scheduled tasks here
    # For example:
    # scheduler.add_job(some_function, 'interval', hours=24)
    
    return scheduler

async def _run_daily_report_async():
    """Generate and send the daily report"""
    print("Generating daily report...")
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "data", "config.json")
    if not os.path.exists(config_path):
        print("Config file not found")
        return
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Get webhook URL and OpenAI API key
    webhook_url = config.get("webhooks", {}).get("report")
    openai_api_key = config.get("openai_api_key")
    
    if not webhook_url:
        print("Daily report webhook URL not configured")
        return
    
    # Get today's summaries
    today = datetime.now().strftime("%Y-%m-%d")
    summaries_path = os.path.join(os.path.dirname(__file__), "data", "summaries.json")
    
    if not os.path.exists(summaries_path):
        print("Summaries file not found")
        await send_discord_message(
            webhook_url=webhook_url,
            content="**Daily YouTube Summary Report**",
            description="No new videos summarized today."
        )
        return
    
    with open(summaries_path, "r") as f:
        all_summaries = json.load(f)
    
    today_summaries = all_summaries.get(today, [])
    
    # Generate the report
    report = await generate_daily_report(today_summaries, openai_api_key)
    
    # Send the report to Discord
    await send_discord_message(
        webhook_url=webhook_url,
        content="**Daily YouTube Summary Report**",
        description=report
    )
    
    print("Daily report sent successfully")

def run_daily_report():
    """Run the daily report in an asyncio event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_run_daily_report_async())
    except Exception as e:
        print(f"Error running daily report: {e}")
    finally:
        loop.close() 