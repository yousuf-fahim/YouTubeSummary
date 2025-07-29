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
        if endpoint == "/process" and method == "POST":
            if data and (data.get("url") or data.get("youtube_url")):
                url = data.get("url") or data.get("youtube_url")
                result = test_video_processing(url)
                return result, None
        
        elif endpoint == "/channels" and method == "GET":
            result = get_local_channels()
            return result, None
        
        elif endpoint == "/channels/add" and method == "POST":
            if data and (data.get("channel_id") or data.get("channel_input")):
                channel = data.get("channel_id") or data.get("channel_input")
                result = add_local_channel(channel)
                return result, None
        
        elif endpoint.startswith("/channels/") and method == "DELETE":
            channel_id = endpoint.split("/")[-1]
            result = remove_local_channel(channel_id)
            return result, None
        
        elif endpoint == "/config" and method == "GET":
            result = get_local_config()
            return result, None
        
        elif endpoint == "/test" and method == "POST":
            result = test_discord_webhook()
            return result, None
        
        elif endpoint == "/reports/trigger" and method == "POST":
            result = trigger_daily_report()
            return result, None
        
        elif endpoint == "/summaries" and method == "GET":
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
                    result, error = call_backend_api("/process", "POST", {
                        "url": youtube_url
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
        
        # Load channels data with improved caching and refresh logic
        should_refresh = (
            st.session_state.channels_data is None or 
            refresh_btn or 
            (auto_refresh and (
                st.session_state.last_refresh is None or 
                time.time() - st.session_state.last_refresh > 300  # 5 minutes
            ))
        )
        
        if should_refresh:
            with st.spinner("Loading channels..."):
                # Try backend API
                channels_data, error = call_backend_api("/channels")
                
                if error:
                    # Fallback to local function
                    try:
                        from local_functions import get_local_channels
                        local_result = get_local_channels()
                        if local_result.get("status") == "success":
                            channels_data = {
                                "channels": {
                                    "tracked_channels": local_result.get("channels", []),
                                    "last_videos": local_result.get("last_videos", {})
                                }
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
            # Parse channel data with improved error handling
            channels = []
            last_videos = {}
            
            if channels_data:
                # Handle different API response formats
                if "channels" in channels_data and isinstance(channels_data["channels"], dict):
                    # Backend format: {"success": true, "channels": {"@TED": {"name": "@TED", "id": "@TED"}}, "count": 4}
                    backend_channels = channels_data["channels"]
                    if "tracked_channels" in backend_channels:
                        # Nested format: {"channels": {"tracked_channels": [...], "last_videos": {...}}}
                        channels = backend_channels.get("tracked_channels", [])
                        last_videos = backend_channels.get("last_videos", {})
                    else:
                        # Direct backend format: convert dict to list
                        channels = list(backend_channels.keys())
                        last_videos = {}
                elif "tracked_channels" in channels_data:
                    # Direct format: {"tracked_channels": [...], "last_videos": {...}}
                    channels = channels_data.get("tracked_channels", [])
                    last_videos = channels_data.get("last_videos", {})
                elif isinstance(channels_data.get("channels"), list):
                    # Local format with list
                    channels = channels_data.get("channels", [])
                    last_videos = channels_data.get("last_videos", {})
            
            # Clean and validate channel data
            if isinstance(channels, list):
                channels = [
                    ch for ch in channels 
                    if ch and isinstance(ch, str) and ch not in ["tracked_channels", "last_videos"]
                ]
            else:
                channels = []
            
            # Display channel count and last refresh time
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{len(channels)} channels tracked**")
            with col2:
                if st.session_state.last_refresh:
                    refresh_time = datetime.fromtimestamp(st.session_state.last_refresh).strftime("%H:%M:%S")
                    st.caption(f"Last updated: {refresh_time}")
            
            # Display channels with improved UI
            if channels:
                # Pagination settings
                if 'channel_page' not in st.session_state:
                    st.session_state.channel_page = 0
                
                channels_per_page = 5
                total_pages = (len(channels) - 1) // channels_per_page + 1
                start_idx = st.session_state.channel_page * channels_per_page
                end_idx = start_idx + channels_per_page
                current_channels = channels[start_idx:end_idx]
                
                # Pagination controls (only show if more than 1 page)
                if total_pages > 1:
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        if st.button("⬅️ Previous", disabled=st.session_state.channel_page == 0, use_container_width=True):
                            st.session_state.channel_page -= 1
                            st.rerun()
                    
                    with col2:
                        st.markdown(f"<div style='text-align: center; padding: 10px;'>Page {st.session_state.channel_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
                    
                    with col3:
                        if st.button("Next ➡️", disabled=st.session_state.channel_page >= total_pages - 1, use_container_width=True):
                            st.session_state.channel_page += 1
                            st.rerun()
                
                # Display channels in a clean table format
                for i, channel in enumerate(current_channels):
                    with st.container():
                        st.markdown("---")
                        col1, col2, col3 = st.columns([3, 4, 1])
                        
                        with col1:
                            st.markdown(f"**{channel}**")
                        
                        with col2:
                            # Get latest video info with better error handling
                            if channel in last_videos and isinstance(last_videos.get(channel), dict):
                                video_info = last_videos[channel]
                                title = video_info.get('title', '').strip()
                                published = video_info.get('published', '').strip()
                                
                                if title and title != 'None':
                                    # Truncate long titles
                                    display_title = title[:60] + "..." if len(title) > 60 else title
                                    st.markdown(f"🎥 **{display_title}**")
                                    if published:
                                        st.caption(f"� {published}")
                                else:
                                    st.markdown("📭 *No recent videos*")
                            else:
                                st.markdown("� *No video data*")
                        
                        with col3:
                            if st.button("🗑️", key=f"remove_{start_idx + i}", help="Remove channel", use_container_width=True):
                                with st.spinner("Removing..."):
                                    remove_result, remove_error = call_backend_api(f"/channels/remove", "POST", {"channel_id": channel})
                                    
                                    if remove_error:
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
            
            # Add new channel section with improved UI
            st.markdown("---")
            st.subheader("➕ Add New Channel")
            
            with st.form("add_channel_form", clear_on_submit=True):
                new_channel = st.text_input(
                    "Channel URL or ID:",
                    placeholder="https://www.youtube.com/@channelname or UC1234567890",
                    help="Enter YouTube channel URL or channel ID"
                )
                
                submitted = st.form_submit_button("Add Channel", type="primary", use_container_width=True)
                
                if submitted and new_channel:
                    with st.spinner("Adding channel..."):
                        add_result, add_error = call_backend_api("/channels/add", "POST", {
                            "channel_id": new_channel,
                            "channel_name": new_channel
                        })
                        
                        if add_error:
                            # Fallback to local function
                            try:
                                from local_functions import add_local_channel
                                add_result = add_local_channel(new_channel)
                                
                                if add_result.get("status") == "success":
                                    st.success("✅ Channel added successfully!")
                                    st.session_state.channels_data = None
                                    st.rerun()
                                else:
                                    st.error(f"❌ {add_result.get('message', 'Addition failed')}")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                        else:
                            if add_result and add_result.get("success"):
                                st.success("✅ Channel added successfully!")
                                st.session_state.channels_data = None
                                st.rerun()
                            else:
                                st.error(f"❌ {add_result.get('error', 'Addition failed') if add_result else 'No response'}")
    
    # Tab 3: Automation Monitoring  
    with tab3:
        st.header("🤖 Automation Monitoring")
        
        st.info("🚀 **Your YouTube Summary Bot is now fully automated!** It monitors all tracked channels every 30 minutes and processes new videos automatically.")
        
        # Get automation status
        try:
            backend_url = get_backend_url()
            if backend_url:
                response = requests.get(f"{backend_url}/monitoring/status", timeout=15)
                if response.status_code == 200:
                    try:
                        status_data = response.json()
                        
                        # Handle both new format (success: True) and old format (status: "success")
                        is_success = status_data.get("success") == True or status_data.get("status") == "success"
                        
                        if is_success:
                            monitoring = status_data.get("monitoring", {})
                            
                            # Get channel count from channels API
                            channel_count = 0
                            try:
                                channels_response = requests.get(f"{backend_url}/channels", timeout=5)
                                if channels_response.status_code == 200:
                                    channels_data = channels_response.json()
                                    if "channels" in channels_data and isinstance(channels_data["channels"], dict):
                                        # Backend returns: {"success": true, "channels": {"@TED": {...}, "@veritasium": {...}}, "count": 4}
                                        backend_channels = channels_data["channels"]
                                        channel_count = len(backend_channels)
                                    elif "count" in channels_data:
                                        # Use the count field directly
                                        channel_count = channels_data["count"]
                            except:
                                channel_count = status_data.get("channels_count", 0)
                            
                            # Display status in columns
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("📺 Channels Monitored", channel_count)
                            
                            with col2:
                                scheduler_running = monitoring.get("scheduler_running", False)
                                # If scheduler_running is not available, check if monitoring is enabled
                                if not scheduler_running and monitoring.get("enabled"):
                                    scheduler_running = True  # Assume running if monitoring is enabled
                                status_color = "🟢" if scheduler_running else "🔴"
                                st.metric("🤖 Automation Status", f"{status_color} {'Running' if scheduler_running else 'Stopped'}")
                            
                            with col3:
                                next_check = monitoring.get("next_check")
                                if next_check and next_check != "Not implemented yet":
                                    next_time = next_check.split("T")[1][:8] if "T" in next_check else next_check
                                    st.metric("⏰ Next Check", next_time)
                                else:
                                    # Show interval instead if next_check is not available
                                    interval = monitoring.get("interval_minutes", 30)
                                    st.metric("⏰ Check Interval", f"Every {interval} min")
                            
                            # Control buttons
                            st.subheader("🎛️ Automation Controls")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if st.button("▶️ Start Automation", help="Start automated channel monitoring"):
                                    try:
                                        start_response = requests.post(f"{backend_url}/monitoring/trigger", timeout=10)
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
                                        stop_response = requests.post(f"{backend_url}/monitoring/trigger", timeout=10)
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
                                            check_response = requests.post(f"{backend_url}/monitoring/trigger", timeout=60)
                                            if check_response.status_code == 200:
                                                st.success("✅ Manual check completed!")
                                                st.rerun()
                                            else:
                                                st.error("❌ Manual check failed")
                                    except Exception as e:
                                        st.error(f"❌ Error: {e}")
                            
                            # Show tracked channels
                            st.subheader("📋 Monitored Channels")
                            
                            # Get the actual tracked channels from the channels API
                            tracked_channels = []
                            try:
                                channels_response = requests.get(f"{backend_url}/channels", timeout=5)
                                if channels_response.status_code == 200:
                                    channels_data = channels_response.json()
                                    if "channels" in channels_data and isinstance(channels_data["channels"], dict):
                                        # Backend returns: {"success": true, "channels": {"@TED": {...}, "@veritasium": {...}}, "count": 4}
                                        backend_channels = channels_data["channels"]
                                        tracked_channels = list(backend_channels.keys())
                            except:
                                tracked_channels = []
                            
                            if tracked_channels:
                                # Show channels in a compact format
                                for i, channel in enumerate(tracked_channels[:10], 1):  # Show max 10
                                    st.text(f"{i}. {channel}")
                                
                                if len(tracked_channels) > 10:
                                    st.caption(f"... and {len(tracked_channels) - 10} more channels")
                                    st.info("💡 Go to the Channel Tracking tab to see all channels and manage them")
                            else:
                                st.info("📭 No channels being monitored. Add channels in the Channel Tracking tab.")
                            
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
        config_data, config_error = call_backend_api("/config")
        
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
                test_result, test_error = call_backend_api("/test", "POST", {
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
        summaries_data, summaries_error = call_backend_api("/summaries")
        
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
                report_result, report_error = call_backend_api("/reports/trigger", "POST")
                
                if report_error:
                    st.error(f"❌ Report generation failed: {report_error}")
                else:
                    if report_result and report_result.get("success"):
                        st.success("✅ Daily report generated and sent to Discord!")
                    else:
                        st.error(f"❌ {report_result.get('error', 'Report generation failed') if report_result else 'No response from backend'}")

if __name__ == "__main__":
    main()
