import streamlit as st
import os
import sys
import re
import asyncio
import json
import time
import requests
from datetime import datetime

# Add project root to path for shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Try to load environment variables from .env in development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import local fallback functions
try:
    from local_functions import (
        test_video_processing, get_local_channels, add_local_channel, 
        remove_local_channel, get_local_config, test_discord_webhook,
        trigger_daily_report, get_recent_summaries
    )
    LOCAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    LOCAL_FUNCTIONS_AVAILABLE = False

# Set page configuration
st.set_page_config(
    page_title="YouTube Summary Bot", 
    page_icon="🤖", 
    layout="wide"
)

def get_backend_url():
    """Get backend URL from environment"""
    # Railway deployment
    backend_url = os.getenv("BACKEND_URL")
    if backend_url:
        return backend_url
    
    # Local development fallback - return None to trigger local mode
    return None

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if not url:
        return None
    youtube_regex = r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

def validate_youtube_url(url):
    """Validate YouTube URL format"""
    if not url:
        return False
    return bool(extract_video_id(url))

def call_backend_api(endpoint, method="GET", data=None):
    """Make API calls to backend with error handling and local fallback"""
    backend_url = get_backend_url()
    
    # If no backend URL, use local testing mode
    if not backend_url:
        if LOCAL_FUNCTIONS_AVAILABLE:
            return handle_local_fallback(endpoint, method, data)
        else:
            return None, "Backend not available and local functions not loaded"
    
    try:
        url = f"{backend_url}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            return None, f"Unsupported method: {method}"
        
        if response.status_code == 200:
            try:
                return response.json(), None
            except:
                return {"success": True}, None
        else:
            # Try local fallback on API error
            if LOCAL_FUNCTIONS_AVAILABLE:
                return handle_local_fallback(endpoint, method, data)
            return None, f"API error: {response.status_code}"
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.ConnectionError:
        # Try local fallback on connection error
        if LOCAL_FUNCTIONS_AVAILABLE:
            return handle_local_fallback(endpoint, method, data)
        return None, "Cannot connect to backend"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

def handle_local_fallback(endpoint, method, data):
    """Handle API calls with local functions"""
    try:
        if endpoint == "/api/manual-summary" and method == "POST":
            if data and data.get("youtube_url"):
                result = test_video_processing(data["youtube_url"])
                return result, None
        
        elif endpoint == "/api/channels" and method == "GET":
            result = get_local_channels()
            return result, None
        
        elif endpoint == "/api/channels/add" and method == "POST":
            if data and data.get("channel_input"):
                result = add_local_channel(data["channel_input"])
                return result, None
        
        elif endpoint.startswith("/api/channels/") and method == "DELETE":
            channel_id = endpoint.split("/")[-1]
            result = remove_local_channel(channel_id)
            return result, None
        
        elif endpoint == "/api/config" and method == "GET":
            result = get_local_config()
            return result, None
        
        elif endpoint == "/api/test" and method == "POST":
            result = test_discord_webhook()
            return result, None
        
        elif endpoint == "/api/webhook/trigger-daily-report" and method == "POST":
            result = trigger_daily_report()
            return result, None
        
        elif endpoint == "/api/summaries" and method == "GET":
            result = get_recent_summaries()
            return result, None
        
        else:
            return None, f"Local fallback not implemented for {endpoint}"
    
    except Exception as e:
        return None, f"Local fallback error: {str(e)}"

def main():
    """Main application"""
    
    # Title and description
    st.title("🤖 YouTube Summary Bot")
    st.markdown("AI-powered video summarization with Discord integration")
    
    # Check backend status
    backend_url = get_backend_url()
    with st.sidebar:
        st.subheader("🔧 System Status")
        
        if backend_url:
            try:
                response = requests.get(f"{backend_url}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ Backend Online")
                    st.info("🌐 Production Mode")
                else:
                    st.error("❌ Backend Issues")
                    if LOCAL_FUNCTIONS_AVAILABLE:
                        st.warning("🔄 Fallback to Local Mode")
                    else:
                        st.error("❌ No Local Fallback")
            except:
                st.error("❌ Backend Offline")
                if LOCAL_FUNCTIONS_AVAILABLE:
                    st.warning("🔄 Using Local Mode")
                else:
                    st.error("❌ No Local Fallback")
        else:
            if LOCAL_FUNCTIONS_AVAILABLE:
                st.info("🏠 Local Development Mode")
                st.success("✅ Local Functions Available")
            else:
                st.error("❌ No Backend or Local Functions")
    
    # Create tabs for different functions
    tab1, tab2, tab3, tab4 = st.tabs(["📹 Process Video", "📋 Channel Tracking", "⚙️ Configuration", "📊 Reports"])
    
    # Tab 1: Process Individual Video
    with tab1:
        st.header("Process Individual Video")
        
        # YouTube URL input
        youtube_url = st.text_input(
            "Enter YouTube URL:",
            placeholder="https://www.youtube.com/watch?v=...",
            help="Paste a YouTube video URL to get AI summary"
        )
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            process_btn = st.button("🚀 Process Video", type="primary")
        
        with col2:
            sample_btn = st.button("📝 Try Sample Video")
        
        # Sample video button
        if sample_btn:
            youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            st.rerun()
        
        # Process video
        if process_btn and youtube_url:
            if not validate_youtube_url(youtube_url):
                st.error("❌ Invalid YouTube URL format")
            else:
                video_id = extract_video_id(youtube_url)
                
                with st.spinner("Processing video... This may take a few minutes."):
                    # Call backend API for manual summary
                    result, error = call_backend_api("/api/manual-summary", "POST", {
                        "youtube_url": youtube_url
                    })
                    
                    if error:
                        st.error(f"❌ Processing failed: {error}")
                    elif result:
                        if result.get("success"):
                            st.success("✅ Video processed successfully!")
                            
                            # Display results
                            if "transcript" in result:
                                with st.expander("📄 Transcript"):
                                    st.text_area("", result["transcript"], height=200)
                            
                            if "summary" in result:
                                with st.expander("📋 AI Summary", expanded=True):
                                    st.markdown(result["summary"])
                            
                            if "discord_sent" in result:
                                if result["discord_sent"]:
                                    st.info("📢 Results sent to Discord")
                        else:
                            st.error(f"❌ {result.get('error', 'Unknown error')}")
                    else:
                        st.error("❌ No response from backend")
    
    # Tab 2: Channel Tracking
    with tab2:
        st.header("Channel Tracking")
        
        # Get current tracked channels
        channels_data, error = call_backend_api("/api/channels")
        
        if error:
            st.error(f"❌ Cannot load channels: {error}")
        else:
            channels = channels_data.get("channels", []) if channels_data else []
            last_videos = channels_data.get("last_videos", {}) if channels_data else {}
            
            st.subheader(f"📺 Tracked Channels ({len(channels)})")
            
            # Display channels
            if channels:
                for channel in channels:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{channel}**")
                        # Show last video info if available
                        if channel in last_videos:
                            last_video = last_videos[channel]
                            st.write(f"🎥 Last: {last_video.get('title', 'Unknown')}")
                    with col2:
                        if channel in last_videos:
                            st.write(f"📅 {last_videos[channel].get('published', 'Unknown')}")
                        else:
                            st.write("No recent videos")
                    with col3:
                        if st.button("🗑️", key=f"remove_{channel}", help="Remove channel"):
                            # Remove channel using DELETE endpoint
                            remove_result, remove_error = call_backend_api(f"/api/channels/{channel}", "DELETE")
                            if remove_error:
                                st.error(f"❌ Removal failed: {remove_error}")
                            else:
                                st.success("✅ Channel removed")
                                st.rerun()
            else:
                st.info("No channels currently tracked")
            
            # Add new channel
            st.subheader("➕ Add New Channel")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                new_channel = st.text_input(
                    "Channel URL or ID:",
                    placeholder="https://www.youtube.com/@channelname or UC1234567890",
                    help="Enter YouTube channel URL or channel ID"
                )
            
            with col2:
                add_btn = st.button("Add Channel", type="primary")
            
            if add_btn and new_channel:
                with st.spinner("Adding channel..."):
                    add_result, add_error = call_backend_api("/api/channels/add", "POST", {
                        "channel_input": new_channel,
                        "channel_name": ""  # Backend will auto-detect
                    })
                    
                    if add_error:
                        st.error(f"❌ Addition failed: {add_error}")
                    else:
                        if add_result.get("success"):
                            st.success("✅ Channel added successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ {add_result.get('error', 'Unknown error')}")
    
    # Tab 3: Configuration
    with tab3:
        st.header("Configuration")
        
        st.info("🔒 **Security Notice**: Configuration is now handled via environment variables for better security.")
        
        # Show current configuration status
        config_data, config_error = call_backend_api("/api/config")
        
        if config_error:
            st.error(f"❌ Cannot load configuration: {config_error}")
        else:
            st.subheader("📋 Current Settings")
            
            if config_data:
                # Show environment variable status
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
                    value = config_data.get(var.lower().replace('_', ''))
                    if value and value != "NOT_SET":
                        st.success(f"✅ {var}: Configured")
                    else:
                        st.error(f"❌ {var}: Not configured")
            
            # Test webhook button
            st.subheader("🧪 Test Discord Webhook")
            if st.button("Send Test Message"):
                test_result, test_error = call_backend_api("/api/test", "POST", {
                    "message": "Test message from YouTube Summary Bot frontend"
                })
                
                if test_error:
                    st.error(f"❌ Test failed: {test_error}")
                else:
                    if test_result.get("success"):
                        st.success("✅ Test message sent to Discord!")
                    else:
                        st.error(f"❌ {test_result.get('error', 'Test failed')}")
    
    # Tab 4: Reports & Analytics
    with tab4:
        st.header("Reports & Analytics")
        
        # Get recent summaries
        summaries_data, summaries_error = call_backend_api("/api/summaries")
        
        if summaries_error:
            st.error(f"❌ Cannot load summaries: {summaries_error}")
        else:
            summaries = summaries_data.get("summaries", []) if summaries_data else []
            
            st.subheader(f"📊 Recent Summaries ({len(summaries)})")
            
            if summaries:
                for summary in summaries[-10:]:  # Show last 10
                    with st.expander(f"📹 {summary.get('title', 'Unknown Video')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Channel:** {summary.get('channel', 'Unknown')}")
                            st.write(f"**Date:** {summary.get('timestamp', 'Unknown')}")
                        with col2:
                            if summary.get('video_id'):
                                st.write(f"**Video ID:** `{summary['video_id']}`")
                        
                        if summary.get('summary'):
                            st.markdown("**Summary:**")
                            st.markdown(summary['summary'])
            else:
                st.info("No summaries available")
            
            # Manual daily report trigger
            st.subheader("📅 Daily Report")
            if st.button("🚀 Generate Daily Report Now"):
                with st.spinner("Generating daily report..."):
                    report_result, report_error = call_backend_api("/api/webhook/trigger-daily-report", "POST")
                    
                    if report_error:
                        st.error(f"❌ Report generation failed: {report_error}")
                    else:
                        if report_result.get("success"):
                            st.success("✅ Daily report generated and sent to Discord!")
                        else:
                            st.error(f"❌ {report_result.get('error', 'Report generation failed')}")

if __name__ == "__main__":
    main()
