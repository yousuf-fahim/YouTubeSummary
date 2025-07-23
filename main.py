#!/usr/bin/env python3
import os
import json
import asyncio
from discord_listener import DiscordListener
from schedule import setup_scheduler
from fastapi import FastAPI, Body, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import subprocess
import sys
from transcript import get_transcript, extract_video_id
from summarize import chunk_and_summarize, generate_daily_report
from discord_utils import send_discord_message, send_file_to_discord
from supabase_utils import get_config as get_supabase_config, save_config as save_supabase_config
from supabase_utils import get_all_summaries as get_all_supabase_summaries
from pydantic import BaseModel
from datetime import datetime
import pytz

# Create FastAPI app for the API endpoints
app = FastAPI(title="YouTube Summary Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class WebhookModel(BaseModel):
    content: str = ""
    embeds: list = []
    
# Load config
def load_config():
    # Try to get config from Supabase first
    supabase_config = get_supabase_config()
    if supabase_config:
        # Ensure webhook_auth_token exists
        if "webhook_auth_token" not in supabase_config:
            supabase_config["webhook_auth_token"] = os.urandom(16).hex()  # Generate a random token
            save_supabase_config(supabase_config)
        return supabase_config
    
    # Fall back to local file if Supabase config not available
    os.makedirs("data", exist_ok=True)
    config_path = os.path.join("data", "config.json")
    
    if not os.path.exists(config_path):
        default_config = {
            "openai_api_key": "",
            "webhooks": {
                "yt_uploads": "",
                "yt_transcripts": "",
                "yt_summaries": "",
                "daily_report": ""
            },
            "prompts": {
                "summary_prompt": "",
                "daily_report_prompt": ""
            },
            "webhook_auth_token": os.urandom(16).hex()  # Generate a random token
        }
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        return default_config
    
    with open(config_path, "r") as f:
        try:
            config = json.load(f)
            # Ensure webhook_auth_token exists
            if "webhook_auth_token" not in config:
                config["webhook_auth_token"] = os.urandom(16).hex()  # Generate a random token
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
            return config
        except json.JSONDecodeError:
            return {
                "openai_api_key": "",
                "webhooks": {
                    "yt_uploads": "",
                    "yt_transcripts": "",
                    "yt_summaries": "",
                    "daily_report": ""
                },
                "prompts": {
                    "summary_prompt": "",
                    "daily_report_prompt": ""
                },
                "webhook_auth_token": os.urandom(16).hex()  # Generate a random token
            }

# Save config
def save_config(config):
    # Save to Supabase
    save_supabase_config(config)
    
    # Also save locally as backup
    os.makedirs("data", exist_ok=True)
    config_path = os.path.join("data", "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

# Auth dependency for webhooks
async def verify_token(request: Request):
    config = load_config()
    auth_token = config.get("webhook_auth_token", "")
    
    if not auth_token:
        raise HTTPException(status_code=500, detail="Webhook authentication not configured")
    
    token = request.headers.get("Authorization")
    if not token or token != f"Bearer {auth_token}":
        raise HTTPException(status_code=401, detail="Invalid authorization token")
    
    return True

# API endpoints for config
@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def update_config(config: ConfigModel):
    current_config = load_config()
    
    # Update the config with the new values
    updated_config = current_config.copy()
    updated_config["openai_api_key"] = config.openai_api_key
    updated_config["webhooks"] = {
        "yt_uploads": config.webhooks.get("yt_uploads", ""),
        "yt_transcripts": config.webhooks.get("yt_transcripts", ""),
        "yt_summaries": config.webhooks.get("yt_summaries", ""),
        "daily_report": config.webhooks.get("daily_report", "")
    }
    
    save_config(updated_config)
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
        config = load_config()
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
            # Filter for summaries from today
            today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            for summary in all_summaries:
                created_at = datetime.fromisoformat(summary.get("created_at").replace('Z', '+00:00'))
                if created_at >= today_date:
                    # Format summary for the daily report
                    video_id = summary.get("video_id")
                    formatted_summary = {
                        "title": summary.get("title", "Untitled"),
                        "points": summary.get("points", []),
                        "summary": summary.get("summary_text", ""),
                        "noteworthy_mentions": summary.get("noteworthy_mentions", []),
                        "verdict": summary.get("verdict", ""),
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
            await send_discord_message(
                daily_report_webhook,
                title="Daily Summary Report",
                description="No new videos were summarized today.",
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
    
    config = load_config()
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
def get_webhook_token():
    """Get the current webhook authentication token"""
    config = load_config()
    token = config.get("webhook_auth_token", "")
    
    if not token:
        # Generate a new token
        token = os.urandom(16).hex()
        config["webhook_auth_token"] = token
        save_config(config)
        
    return {"token": token}

@app.post("/api/webhook-token/regenerate")
def regenerate_webhook_token():
    """Regenerate the webhook authentication token"""
    config = load_config()
    new_token = os.urandom(16).hex()
    config["webhook_auth_token"] = new_token
    save_config(config)
    
    return {"token": new_token}

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
    print("Scheduled daily report triggered")
    await trigger_daily_report(True)

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