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
    # Load from parent directory where .env file is located
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")
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
    # Railway deployment or explicit backend URL
    backend_url = os.getenv("BACKEND_URL")
    if backend_url:
        return backend_url
    
    # Default to working Heroku backend with automation
    return "https://yt-bot-backend-8302f5ba3275.herokuapp.com"

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
                response = requests.get(f"{backend_url}/api/health", timeout=5)
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
        
        # Add scheduler status display
        st.subheader("⏰ Scheduler Status")
        try:
            from local_functions import get_scheduler_status
            status = get_scheduler_status()
            
            if status.get('status') == 'success':
                data = status.get('data', {})
                scheduler_status = data.get('status', 'Unknown')
                
                if scheduler_status == 'running':
                    st.success(f"✅ Scheduler: {scheduler_status}")
                else:
                    st.warning(f"⚠️ Scheduler: {scheduler_status}")
                
                # Daily report timer
                daily_report = data.get('daily_report', {})
                if daily_report and daily_report.get('time_until'):
                    st.info(f"📅 Next Daily Report: {daily_report['time_until']}")
                else:
                    st.info("📅 Daily Report: 18:00 CEST")
                
                # Channel tracking info
                channel_tracking = data.get('channel_tracking', {})
                if channel_tracking:
                    if channel_tracking.get('time_until'):
                        st.info(f"📺 Next Channel Check: {channel_tracking['time_until']}")
                    else:
                        st.info("📺 Channel Tracking: Every 30 min")
                
                timezone = data.get('timezone', 'UTC')
                st.caption(f"🌍 Timezone: {timezone}")
                
            else:
                st.warning("⚠️ Scheduler status unavailable")
                st.caption("Daily reports: 18:00 CEST")
                st.caption("Channel tracking: Every 30 min")
                
        except Exception as e:
            st.warning("⚠️ Scheduler info unavailable")
            st.caption("Daily reports: 18:00 CEST")
            st.caption("Channel tracking: Every 30 min")
    
    # Create tabs for different functions
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📹 Process Video", "📋 Channel Tracking", "🤖 Automation", "⚙️ Configuration", "📊 Reports"])
    
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
        
        # Initialize session state for channels
        if 'channels_data' not in st.session_state:
            st.session_state.channels_data = None
            st.session_state.last_refresh = None
        
        # Add refresh button and auto-refresh logic
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.subheader("📺 Tracked Channels")
        with col2:
            refresh_btn = st.button("🔄 Refresh", help="Refresh channel data")
        with col3:
            auto_refresh = st.checkbox("Auto-refresh", value=False)
        
        # Load channels data (with caching)
        if (st.session_state.channels_data is None or 
            refresh_btn or 
            (auto_refresh and st.session_state.last_refresh is None)):
            
            with st.spinner("Loading channels..."):
                # Try backend first, fallback to local
                channels_data, error = call_backend_api("/api/channels")
                
                if error:
                    # Fallback to local function
                    try:
                        from local_functions import get_local_channels
                        local_result = get_local_channels()
                        if local_result.get("status") == "success":
                            channels_data = {
                                "channels": local_result.get("channels", []),
                                "last_videos": local_result.get("last_videos", {})
                            }
                            error = None
                    except Exception as e:
                        error = f"Backend and local both failed: {e}"
                
                st.session_state.channels_data = channels_data
                st.session_state.last_refresh = time.time()
        else:
            channels_data = st.session_state.channels_data
            error = None
        
        if error:
            st.error(f"❌ Cannot load channels: {error}")
        else:
            # Handle both backend API format and local format
            if channels_data:
                # Backend API format
                if "tracked_channels" in channels_data:
                    channels = channels_data.get("tracked_channels", [])
                    last_videos = channels_data.get("last_videos", {})
                # Local format  
                elif "channels" in channels_data:
                    channels = channels_data.get("channels", [])
                    last_videos = channels_data.get("last_videos", {})
                else:
                    channels = []
                    last_videos = {}
            else:
                channels = []
                last_videos = {}
            
            st.write(f"**{len(channels)} channels tracked**")
            
            # Display channels in a more efficient way
            if channels and channels != ["tracked_channels", "last_videos"]:
                for i, channel in enumerate(channels):
                    # Skip if channel is just a key name
                    if channel in ["tracked_channels", "last_videos"]:
                        continue
                        
                    with st.container():
                        col1, col2, col3 = st.columns([4, 3, 1])
                        with col1:
                            st.write(f"**{channel}**")
                        with col2:
                            if channel in last_videos and isinstance(last_videos[channel], dict) and last_videos[channel].get('title'):
                                st.caption(f"🎥 {last_videos[channel]['title'][:50]}...")
                            else:
                                st.caption("📭 No recent videos")
                        with col3:
                            if st.button("🗑️", key=f"remove_{i}", help="Remove channel"):
                                # Remove channel - try backend first, then local
                                with st.spinner("Removing channel..."):
                                    # Try backend API
                                    remove_result, remove_error = call_backend_api(f"/api/channels/{channel}", "DELETE")
                                    
                                    if remove_error:
                                        # Fallback to local
                                        try:
                                            from local_functions import remove_local_channel
                                            remove_result = remove_local_channel(channel)
                                            if remove_result.get("status") == "success":
                                                st.success("✅ Channel removed")
                                                st.session_state.channels_data = None
                                                st.rerun()
                                            else:
                                                st.error("❌ Removal failed")
                                        except Exception as e:
                                            st.error(f"❌ Error: {e}")
                                    else:
                                        st.success("✅ Channel removed")
                                        st.session_state.channels_data = None
                                        st.rerun()
            else:
                st.info("📭 No channels currently tracked")
            
            # Add new channel
            st.subheader("➕ Add New Channel")
            
            col1, col2 = st.columns([4, 1])
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
                    # Try backend API first
                    add_result, add_error = call_backend_api("/api/channels/add", "POST", {
                        "channel_input": new_channel
                    })
                    
                    if add_error:
                        # Fallback to local function
                        try:
                            from local_functions import add_local_channel
                            add_result = add_local_channel(new_channel)
                            
                            if add_result.get("status") == "success":
                                st.success("✅ Channel added successfully!")
                                # Clear cache to force refresh
                                st.session_state.channels_data = None
                                st.rerun()
                            else:
                                st.error(f"❌ Addition failed: {add_result.get('message', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"❌ Error adding channel: {e}")
                    else:
                        if add_result and add_result.get("success"):
                            st.success("✅ Channel added successfully!")
                            # Clear cache to force refresh
                            st.session_state.channels_data = None
                            st.rerun()
                        else:
                            st.error(f"❌ Addition failed: {add_result.get('error', 'Unknown error') if add_result else 'No response'}")
    
    # Tab 3: Automation Monitoring  
    with tab3:
        st.header("🤖 Automation Monitoring")
        
        st.info("🚀 **Your YouTube Summary Bot is now fully automated!** It monitors all tracked channels every 30 minutes and processes new videos automatically.")
        
        # Get automation status
        try:
            backend_url = get_backend_url()
            if backend_url:
                response = requests.get(f"{backend_url}/api/monitor/status", timeout=15)
                if response.status_code == 200:
                    try:
                        status_data = response.json()
                        
                        if status_data.get("success"):
                            monitoring = status_data.get("monitoring", {})
                            
                            # Display status in columns
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("📺 Channels Monitored", monitoring.get("channels_tracked", 0))
                            
                            with col2:
                                scheduler_running = monitoring.get("scheduler_running", False)
                                status_color = "🟢" if scheduler_running else "🔴"
                                st.metric("🤖 Automation Status", f"{status_color} {'Running' if scheduler_running else 'Stopped'}")
                            
                            with col3:
                                next_check = monitoring.get("next_check")
                                if next_check:
                                    next_time = next_check.split("T")[1][:8] if "T" in next_check else next_check
                                    st.metric("⏰ Next Check", next_time)
                                else:
                                    st.metric("⏰ Next Check", "Not scheduled")
                            
                            # Control buttons
                            st.subheader("🎛️ Automation Controls")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if st.button("▶️ Start Automation", help="Start automated channel monitoring"):
                                    try:
                                        start_response = requests.post(f"{backend_url}/api/monitor/start", timeout=10)
                                        if start_response.status_code == 200:
                                            st.success("✅ Automation started!")
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to start automation")
                                    except Exception as e:
                                        st.error(f"❌ Error: {e}")
                            
                            with col2:
                                if st.button("⏹️ Stop Automation", help="Stop automated channel monitoring"):
                                    try:
                                        stop_response = requests.post(f"{backend_url}/api/monitor/stop", timeout=10)
                                        if stop_response.status_code == 200:
                                            st.success("✅ Automation stopped!")
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to stop automation")
                                    except Exception as e:
                                        st.error(f"❌ Error: {e}")
                            
                            with col3:
                                if st.button("🔄 Check Now", help="Manually trigger channel checking"):
                                    try:
                                        with st.spinner("Checking channels..."):
                                            check_response = requests.post(f"{backend_url}/api/monitor/check-now", timeout=60)
                                            if check_response.status_code == 200:
                                                st.success("✅ Manual check completed!")
                                                st.rerun()
                                            else:
                                                st.error("❌ Manual check failed")
                                    except Exception as e:
                                        st.error(f"❌ Error: {e}")
                            
                            # Show tracked channels
                            st.subheader("📋 Monitored Channels")
                            channels = monitoring.get("channels", [])
                            if channels:
                                for i, channel in enumerate(channels, 1):
                                    st.text(f"{i}. {channel}")
                            else:
                                st.info("No channels being monitored")
                            
                            # Automation info
                            st.subheader("ℹ️ How It Works")
                            st.markdown("""
                            **Your bot automatically:**
                            - 🕐 Checks all tracked channels every 30 minutes
                            - 📡 Fetches latest videos via YouTube RSS feeds  
                            - 📝 Extracts transcripts and generates AI summaries
                            - 📤 Sends Discord notifications with summaries
                            - 💾 Saves everything to your database
                            
                            **No manual intervention required!** Just sit back and receive automated video summaries.
                            """)
                        else:
                            st.error("❌ Failed to get automation status")
                            st.info("💡 The automation system may still be starting up after deployment")
                    except ValueError:
                        st.error("❌ Invalid response from backend")
                        st.info("💡 Backend may still be deploying. Try refreshing in a minute.")
                elif response.status_code == 404:
                    st.error("❌ Automation endpoints not found")
                    st.info("💡 Backend deployment may not include automation features yet")
                else:
                    st.error(f"❌ Backend error: {response.status_code}")
                    st.info("💡 Try refreshing the page or check backend logs")
            else:
                st.error("❌ Backend URL not configured")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend")
            st.info("💡 Backend may be deploying or temporarily unavailable")
        except requests.exceptions.Timeout:
            st.error("❌ Backend request timed out")
            st.info("💡 Backend may be slow to respond during startup")
        except Exception as e:
            st.error(f"❌ Error connecting to backend: {e}")
            st.info("💡 Check your internet connection and try again")
    
    # Tab 4: Configuration
    with tab4:
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
                    "DISCORD_WEBHOOK_UPLOADS",
                    "DISCORD_WEBHOOK_TRANSCRIPTS",
                    "DISCORD_WEBHOOK_SUMMARIES",
                    "DISCORD_WEBHOOK_DAILY_REPORT"
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
    
    # Tab 5: Reports & Analytics
    with tab5:
        st.header("Reports & Analytics")
        
        # Get recent summaries
        summaries_data, summaries_error = call_backend_api("/api/summaries")
        
        if summaries_error:
            st.error(f"❌ Cannot load summaries: {summaries_error}")
            # Try local fallback
            try:
                from local_functions import get_recent_summaries
                local_summaries = get_recent_summaries()
                if local_summaries.get("status") == "success":
                    summaries = local_summaries.get("summaries", [])
                    summaries_error = None
                else:
                    summaries = []
            except:
                summaries = []
        else:
            # Handle different response formats
            if summaries_data:
                if isinstance(summaries_data, dict):
                    summaries = summaries_data.get("summaries", [])
                elif isinstance(summaries_data, list):
                    summaries = summaries_data
                else:
                    summaries = []
            else:
                summaries = []
        
        # Filter out invalid summaries (like "None" strings)
        valid_summaries = []
        if summaries:
            for summary in summaries:
                if (isinstance(summary, dict) and 
                    summary.get('title') and 
                    summary.get('title') != 'None' and
                    summary.get('summary')):
                    valid_summaries.append(summary)
        
        st.subheader(f"📊 Recent Summaries ({len(valid_summaries)})")
        
        if valid_summaries:
            for summary in valid_summaries[-10:]:  # Show last 10
                with st.expander(f"📹 {summary.get('title', 'Unknown Video')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Channel:** {summary.get('channel', 'Unknown')}")
                        if summary.get('timestamp'):
                            st.write(f"**Date:** {summary.get('timestamp')}")
                        elif summary.get('created_at'):
                            st.write(f"**Date:** {summary.get('created_at')}")
                    with col2:
                        if summary.get('video_id'):
                            st.write(f"**Video ID:** `{summary['video_id']}`")
                            youtube_url = f"https://www.youtube.com/watch?v={summary['video_id']}"
                            st.markdown(f"**[🔗 Watch on YouTube]({youtube_url})**")
                    
                    if summary.get('summary'):
                        st.markdown("**Summary:**")
                        st.markdown(summary['summary'])
        else:
            st.info("📭 No summaries available yet")
            st.markdown("""
            **To generate summaries:**
            1. Add channels in the "Channel Tracking" tab
            2. Process videos manually in the "Process Video" tab, or
            3. Enable automation in the "Automation" tab to process new videos automatically
            """)
        
        # Manual daily report trigger
        st.subheader("📅 Daily Report")
        if st.button("🚀 Generate Daily Report Now"):
            with st.spinner("Generating daily report..."):
                report_result, report_error = call_backend_api("/api/webhook/trigger-daily-report", "POST")
                
                if report_error:
                    st.error(f"❌ Report generation failed: {report_error}")
                else:
                    if report_result and report_result.get("success"):
                        st.success("✅ Daily report generated and sent to Discord!")
                    else:
                        st.error(f"❌ {report_result.get('error', 'Report generation failed') if report_result else 'No response from backend'}")

if __name__ == "__main__":
    main()
