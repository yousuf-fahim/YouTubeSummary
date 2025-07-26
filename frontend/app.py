import streamlit as st
import os
import sys
import re
import asyncio
import json
import time
import requests
import ssl

# YouTube Summary Bot - Railway Deployment v3.0
# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Only load dotenv for local development, not in production
if not hasattr(st, 'secrets') or os.getenv('STREAMLIT_SHARING', 'false').lower() != 'true':
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available in production, that's fine

# Set environment variables from Streamlit secrets before importing shared modules
try:
    if hasattr(st, 'secrets') and st.secrets:
        # Set all secrets as environment variables for shared modules
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ[key] = value
        
        # Also handle nested secrets
        try:
            if "general" in st.secrets:
                for key, value in st.secrets["general"].items():
                    if isinstance(value, str):
                        os.environ[key] = value
        except:
            pass
except:
    # No secrets available - this is fine for Railway deployment with env vars
    pass

def get_backend_url():
    """Get backend URL from environment or secrets"""
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and st.secrets:
            # Try direct access first
            if "BACKEND_URL" in st.secrets:
                return st.secrets["BACKEND_URL"]
            # Try nested access
            if "general" in st.secrets and "backend_url" in st.secrets["general"]:
                return st.secrets["general"]["backend_url"]
    except:
        pass
    
    # Try environment variable (for Railway/other platforms)
    backend_url = os.getenv("BACKEND_URL")
    if backend_url:
        return backend_url
    
    # Default URLs based on environment
    if os.getenv("RAILWAY_ENVIRONMENT"):
        # Railway deployment - no backend by default
        return None
    elif os.getenv("STREAMLIT_SHARING"):
        # Streamlit Cloud - no backend by default
        return None
    else:
        # Local development
        return "http://localhost:8001"

@st.cache_data(ttl=30)  # Cache for 30 seconds
def check_service_status(backend_url):
    """Check backend and scheduler status with caching"""
    backend_status = "❌ Offline"
    scheduler_status = "❌ Offline"
    
    if backend_url:
        try:
            response = requests.get(f"{backend_url}/api/health", timeout=5)
            if response.status_code == 200:
                backend_status = "✅ Online"
            else:
                backend_status = "⚠️ Issues"
        except:
            backend_status = "❌ Offline"
        
        try:
            scheduler_response = requests.get(f"{backend_url}/api/scheduler/status", timeout=5)
            if scheduler_response.status_code == 200:
                scheduler_status = "✅ Active"
            else:
                scheduler_status = "⚠️ Issues"
        except:
            scheduler_status = "❌ Offline"
    else:
        backend_status = "⚠️ Not Configured"
        scheduler_status = "⚠️ Not Configured"
    
    return backend_status, scheduler_status

def sanitize_filename(title):
    """Convert video title to safe filename"""
    if not title:
        return "unknown_video"
    # Remove invalid characters for filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with underscores and limit length
    sanitized = sanitized.replace(' ', '_')
    # Limit length to avoid filesystem issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized

# Try to import shared modules with fallback
try:
    from shared.transcript import get_transcript, extract_video_id
    from shared.summarize import chunk_and_summarize, DEFAULT_SUMMARY_PROMPT, DEFAULT_DAILY_REPORT_PROMPT
    from shared.discord_utils import send_discord_message, send_file_to_discord
    from shared.discord_listener import DiscordListener
    from shared.supabase_utils import get_config as get_supabase_config, save_config as save_supabase_config
    from shared.supabase_utils import get_transcript as get_supabase_transcript, get_summary as get_supabase_summary
    from shared.youtube_tracker import get_latest_videos_from_channel, load_tracking_data, save_tracking_data
    SHARED_MODULES_AVAILABLE = True
except ImportError as e:
    # In production, shared modules might not be available due to missing dependencies
    # We'll use API calls to the backend instead
    SHARED_MODULES_AVAILABLE = False
    st.warning(f"Shared modules not available: {e}. Using API mode.")
    
    # Define fallback functions that use API calls
    def get_transcript(url):
        backend_url = get_backend_url()
        return requests.post(f"{backend_url}/api/transcript", json={"url": url})
        
    def extract_video_id(url):
        import re
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:v\/|v=|youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    # Default prompts
    DEFAULT_SUMMARY_PROMPT = "Summarize this video transcript"
    DEFAULT_DAILY_REPORT_PROMPT = "Create a daily report"
    
    # Additional fallback functions
    def get_supabase_config():
        return None
        
    def save_supabase_config(config):
        return False
        
    def get_supabase_transcript(video_id):
        return None
        
    def get_supabase_summary(video_id):
        return None
        
    async def send_discord_message(webhook_url, content):
        backend_url = get_backend_url()
        response = requests.post(f"{backend_url}/api/discord/send", 
                               json={"webhook_url": webhook_url, "content": content})
        return response.json() if response.status_code == 200 else None
        
    class DiscordListener:
        def __init__(self):
            pass
        def check_new_videos(self):
            return []
        def get_channel_info(self, channel_id):
            return None
            
    def get_latest_videos_from_channel(channel_id, max_results=5):
        backend_url = get_backend_url()
        response = requests.get(f"{backend_url}/api/youtube/channel/{channel_id}/videos", 
                              params={"max_results": max_results})
        return response.json() if response.status_code == 200 else []
        
    def load_tracking_data():
        return {"channels": []}
        
    def save_tracking_data(data):
        return True

st.set_page_config(
    page_title="YouTube Summary Bot", 
    page_icon="🤖", 
    layout="wide",
    menu_items={
        'Get Help': 'https://github.com/yousuf-fahim/YouTubeSummary',
        'Report a bug': "https://github.com/yousuf-fahim/YouTubeSummary/issues",
        'About': "AI-powered YouTube video summarization with Discord integration"
    }
)

# Set up session state for caching
if "transcripts" not in st.session_state:
    st.session_state.transcripts = {}
    
# Store transcript error messages
if "transcript_error" not in st.session_state:
    st.session_state.transcript_error = None

def load_config():
    """Load configuration from Supabase or config.json"""
    # Try to get config from Supabase first if modules are available
    if SHARED_MODULES_AVAILABLE:
        try:
            supabase_config = get_supabase_config()
            if supabase_config:
                # Ensure config has all required fields
                if "prompts" not in supabase_config:
                    supabase_config["prompts"] = {
                        "summary_prompt": DEFAULT_SUMMARY_PROMPT,
                        "daily_report_prompt": DEFAULT_DAILY_REPORT_PROMPT
                    }
                if "webhook_auth_token" not in supabase_config:
                    supabase_config["webhook_auth_token"] = ""
                return supabase_config
        except Exception as e:
            st.warning(f"Could not load config from Supabase: {e}")
    
    # Fall back to API call or default config
    backend_url = get_backend_url()
    try:
        response = requests.get(f"{backend_url}/api/config")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.warning(f"Could not load config from backend: {e}")
    
    # Return default config if all else fails
    return {
        "openai_api_key": "",
        "webhooks": {
            "yt_uploads": "",
            "yt_transcripts": "",
            "yt_summaries": "",
            "daily_report": ""
        },
        "prompts": {
            "summary_prompt": DEFAULT_SUMMARY_PROMPT,
            "daily_report_prompt": DEFAULT_DAILY_REPORT_PROMPT
        },
        "webhook_auth_token": ""
    }

def save_config(config):
    """Save configuration to Supabase and local config.json"""
    # Save to Supabase if modules are available
    if SHARED_MODULES_AVAILABLE:
        try:
            save_supabase_config(config)
        except Exception as e:
            st.warning(f"Could not save config to Supabase: {e}")
    
    # Try to save via API as backup
    backend_url = get_backend_url()
    try:
        response = requests.post(f"{backend_url}/api/config", json=config)
        if response.status_code == 200:
            st.success("Configuration saved successfully!")
        else:
            st.warning("Configuration save may have failed.")
    except Exception as e:
        st.warning(f"Could not save config via API: {e}")

def is_valid_youtube_url(url):
    """Check if URL is a valid YouTube URL"""
    pattern = r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]{11}'
    return bool(re.match(pattern, url))

def is_valid_discord_webhook(url):
    """Check if URL is a valid Discord webhook URL"""
    pattern = r'^https://discord\.com/api/webhooks/\d+/[\w-]+$'
    return bool(re.match(pattern, url))

async def get_cached_transcript(url):
    """Get transcript with caching using Supabase"""
    video_id = extract_video_id(url)
    
    # Check if transcript is already in session cache
    if video_id and video_id in st.session_state.transcripts:
        return st.session_state.transcripts[video_id]
    
    # Check if transcript is in Supabase
    if video_id:
        supabase_transcript = get_supabase_transcript(video_id)
        if supabase_transcript:
            transcript = supabase_transcript.get("transcript_text")
            # Save to session cache
            st.session_state.transcripts[video_id] = transcript
            return transcript
    
    # Check if transcript is saved on disk (legacy fallback)
    if video_id:
        transcript_path = f"data/transcripts/{video_id}.txt"
        if os.path.exists(transcript_path):
            with open(transcript_path, 'r') as f:
                transcript = f.read()
                # Save to session cache
                st.session_state.transcripts[video_id] = transcript
                return transcript
    
    # Reset previous error
    st.session_state.transcript_error = None
    
    # Fetch new transcript
    transcript = await get_transcript(url)
    
    # If transcript is None, capture error from stderr
    if transcript is None:
        # Just set a generic error message - details will be printed to console
        st.session_state.transcript_error = "Could not retrieve transcript"
    
    # Save to cache if successful
    if transcript and video_id:
        st.session_state.transcripts[video_id] = transcript
        
        # Save to disk as backup (legacy support)
        os.makedirs("data/transcripts", exist_ok=True)
        with open(f"data/transcripts/{video_id}.txt", 'w') as f:
            f.write(transcript)
    
    return transcript

def test_openai_api_key(api_key):
    """Simple test to check if OpenAI API key is valid"""
    import aiohttp
    
    async def test_key():
        # Create a context that doesn't verify certificates (for development only)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {"role": "user", "content": "Hello, this is a test!"}
                ],
                "max_tokens": 10
            }
            
            try:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        return False
            except:
                return False
    
    return asyncio.run(test_key())

def get_webhook_token():
    """Get the current webhook token or generate a new one"""
    config = load_config()
    token = config.get("webhook_auth_token", "")
    
    # If token is empty, try to get it from the API
    if not token:
        try:
            response = requests.get("http://localhost:8000/api/webhook-token")
            if response.status_code == 200:
                token = response.json().get("token", "")
                # Update the config
                config["webhook_auth_token"] = token
                save_config(config)
        except:
            pass
    
    return token

def regenerate_webhook_token():
    """Regenerate the webhook token"""
    try:
        response = requests.post("http://localhost:8000/api/webhook-token/regenerate")
        if response.status_code == 200:
            token = response.json().get("token", "")
            # Update the config
            config = load_config()
            config["webhook_auth_token"] = token
            save_config(config)
            return token
    except:
        pass
    
    return None

async def test_webhook(webhook_url, message_type="general"):
    """Test a Discord webhook by sending a test message"""
    if not webhook_url:
        return False, "No webhook URL provided"
    
    if not is_valid_discord_webhook(webhook_url):
        return False, "Invalid webhook URL format"
    
    # Different test messages based on webhook type
    if message_type == "transcript":
        title = "📝 Transcript Webhook Test"
        description = "This is a test message for the transcript webhook."
        content = "✅ Your transcript webhook is working correctly!"
        color = 3066993  # Green
    elif message_type == "summary":
        title = "📊 Summary Webhook Test"
        description = "This is a test message for the summary webhook."
        content = "✅ Your summary webhook is working correctly!"
        color = 10181046  # Purple
    elif message_type == "daily_report":
        title = "📅 Daily Report Webhook Test"
        description = "This is a test message for the daily report webhook."
        content = "✅ Your daily report webhook is working correctly!"
        color = 15844367  # Gold
    else:
        title = "🔧 Webhook Test"
        description = "This is a general test message."
        content = "✅ Your webhook is working correctly!"
        color = 3447003  # Blue
    
    # Add test fields
    fields = [
        {"name": "Test Field", "value": "This is a test field"},
        {"name": "Timestamp", "value": time.strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
        {"name": "Status", "value": "Success", "inline": True}
    ]
    
    try:
        # Send test message
        result = await send_discord_message(
            webhook_url,
            content=content,
            title=title,
            description=description,
            fields=fields,
            color=color
        )
        
        if result:
            return True, "Test message sent successfully!"
        else:
            return False, "Failed to send test message. Check console for details."
    except Exception as e:
        return False, f"Error: {str(e)}"

async def test_uploads_webhook(webhook_url):
    """Test the uploads webhook by checking the latest video"""
    if not webhook_url:
        return False, "No webhook URL provided"
    
    if not is_valid_discord_webhook(webhook_url):
        return False, "Invalid webhook URL format"
    
    try:
        # Get test video
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley
        video_id = extract_video_id(test_url)
        
        # Send test message to webhook
        title = "🎬 YouTube Upload Webhook Test"
        description = "This test confirms your YouTube uploads webhook is working correctly."
        content = f"✅ Your YouTube uploads webhook is configured properly! This would trigger processing for: {test_url}"
        
        fields = [
            {"name": "Video ID", "value": video_id, "inline": True},
            {"name": "Action", "value": "This would trigger transcript and summary generation", "inline": False},
            {"name": "Test Info", "value": "This is only a test - no actual processing was performed"}
        ]
        
        result = await send_discord_message(
            webhook_url,
            content=content,
            title=title,
            description=description,
            fields=fields,
            color=5793266  # Green-blue
        )
        
        if result:
            return True, "Test message sent successfully!"
        else:
            return False, "Failed to send test message. Check console for details."
    except Exception as e:
        return False, f"Error: {str(e)}"

async def process_latest_video():
    """Process the latest video from the Discord listener"""
    try:
        discord_listener = DiscordListener()
        result = await discord_listener.process_latest_message(force=True)
        
        if result:
            return True, "Successfully processed the latest video!"
        else:
            return False, "Failed to process the latest video. Check console for details."
    except Exception as e:
        return False, f"Error: {str(e)}"

async def process_notifyme_message():
    """Process a sample NotifyMe message to test the integration"""
    try:
        discord_listener = DiscordListener()
        result = await discord_listener.process_latest_notifyme_message(force=True)
        
        if result:
            return True, "Successfully processed the NotifyMe notification!"
        else:
            return False, "Failed to process the NotifyMe notification. Check console for details."
    except Exception as e:
        return False, f"Error: {str(e)}"

def check_discord_bot_status():
    """Check if Discord bot is running"""
    # Simple check to see if we can find any Discord process
    # This is a simplified version, actual implementation would be more complex
    return True  # Placeholder - always returns True for now

def try_other_video_id_formats(original_id):
    """Try alternate formats for the video ID"""
    # Some common issues with video IDs:
    # - Missing/extra characters
    # - Case sensitivity issues
    # - Commonly mistaken characters (0/O, l/1/I)
    
    suggestions = []
    
    if len(original_id) == 10:  # Missing a character
        suggestions.append(f"{original_id}Q")
        suggestions.append(f"{original_id}A")
    
    if len(original_id) == 12:  # Extra character
        suggestions.append(original_id[0:11])
    
    # Replace common mistaken characters
    if '0' in original_id:
        suggestions.append(original_id.replace('0', 'O'))
    if 'O' in original_id:
        suggestions.append(original_id.replace('O', '0'))
    if 'l' in original_id:
        suggestions.append(original_id.replace('l', '1'))
    if '1' in original_id:
        suggestions.append(original_id.replace('1', 'l'))
    
    return suggestions

def main():
    st.title("🤖 YouTube Summary Bot")
    
    # Check if environment is properly configured
    backend_url = get_backend_url()
    openai_key = os.getenv("OPENAI_API_KEY")
    
    # Status bar at the top with cached status checks
    backend_status, scheduler_status = check_service_status(backend_url)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if openai_key:
            st.success("🔑 OpenAI Configured")
        else:
            st.error("🔑 OpenAI Missing")
    
    with col2:
        if "Online" in backend_status:
            st.success(f"🔗 Backend {backend_status}")
        elif "Issues" in backend_status:
            st.warning(f"🔗 Backend {backend_status}")
        else:
            st.error(f"🔗 Backend {backend_status}")
    
    with col3:
        if "Active" in scheduler_status:
            st.success(f"⏰ Scheduler {scheduler_status}")
        elif "Issues" in scheduler_status:
            st.warning(f"⏰ Scheduler {scheduler_status}")
        else:
            st.error(f"⏰ Scheduler {scheduler_status}")
    
    with col4:
        if st.button("⚙️ Settings"):
            st.info("Settings moved to environment variables for security")
    
    # Main interface tabs
    tab1, tab2, tab3 = st.tabs(["🎬 Video Processor", "📺 Channel Manager", "🧪 System Test"])
    
    with tab1:
        st.header("Process YouTube Videos")
        
        # Quick stats
        backend_url = get_backend_url()
        if backend_url:
            try:
                stats_response = requests.get(f"{backend_url}/api/stats")
                if stats_response.status_code == 200:
                    stats = stats_response.json()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📹 Videos Processed", stats.get("total_videos", 0))
                    with col2:
                        st.metric("📝 Summaries Generated", stats.get("total_summaries", 0))
                    with col3:
                        st.metric("📅 Daily Reports", stats.get("total_reports", 0))
            except:
                pass
        else:
            # Show info about standalone mode
            st.info("ℹ️ **Standalone Mode**: Running without backend. Channel tracking and daily reports require a separate backend service.")
        
        st.divider()
        
        # Input for YouTube URL
        youtube_url = st.text_input(
            "🔗 Enter YouTube URL:",
            placeholder="https://www.youtube.com/watch?v=...",
            key="youtube_url_main"
        )
        
        # Process button and quick actions
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            process_button = st.button("🚀 Process Video", type="primary", disabled=not youtube_url)
        with col2:
            if st.button("📋 Sample Video"):
                st.session_state.sample_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                st.rerun()
        with col3:
            if st.button("🗑️ Clear"):
                st.session_state.youtube_url_main = ""
                st.rerun()
        
        # Handle sample URL
        if hasattr(st.session_state, 'sample_url'):
            youtube_url = st.session_state.sample_url
            del st.session_state.sample_url
            st.rerun()
        
        if youtube_url and process_button:
            if not is_valid_youtube_url(youtube_url):
                st.error("❌ Invalid YouTube URL format")
                if len(youtube_url) == 11 and re.match(r'^[A-Za-z0-9_-]{11}$', youtube_url):
                    st.info(f"💡 Looks like a video ID. Try: https://www.youtube.com/watch?v={youtube_url}")
            else:
                if not openai_key:
                    st.error("❌ OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")
                else:
                    # Process the video
                    with st.status("🔄 Processing video...", expanded=True) as status:
                        video_id = extract_video_id(youtube_url)
                        if video_id:
                            st.write(f"📹 Video ID: `{video_id}`")
                        
                        st.write("📝 Retrieving transcript...")
                        transcript = asyncio.run(get_cached_transcript(youtube_url))
                        
                        if transcript:
                            st.write("✅ Transcript retrieved successfully!")
                            
                            st.write("🤖 Generating AI summary...")
                            summary = asyncio.run(chunk_and_summarize(transcript, openai_key))
                            
                            if summary:
                                st.write("✅ Summary generated successfully!")
                                status.update(label="✅ Video processed successfully!", state="complete")
                                
                                # Display results
                                st.success("🎉 Video processed successfully!")
                                
                                # Show summary in a nice format
                                with st.container():
                                    if summary.get("title"):
                                        st.subheader(f"🎬 {summary['title']}")
                                    
                                    if summary.get("verdict"):
                                        st.info(f"💭 **Verdict:** {summary['verdict']}")
                                    
                                    if summary.get("summary"):
                                        if isinstance(summary["summary"], list):
                                            st.markdown("### 📋 Key Points:")
                                            for point in summary["summary"]:
                                                st.markdown(f"• {point}")
                                        else:
                                            st.markdown("### 📄 Summary:")
                                            st.markdown(summary["summary"])
                                    
                                    if summary.get("noteworthy_mentions"):
                                        st.markdown("### 🎯 Noteworthy Mentions:")
                                        for mention in summary["noteworthy_mentions"]:
                                            st.markdown(f"• {mention}")
                                
                                # Show transcript in expander
                                with st.expander("📜 View Full Transcript"):
                                    st.text_area("Transcript", transcript, height=300, disabled=True)
                                    
                                # Auto-save
                                if video_id:
                                    os.makedirs("data/summaries", exist_ok=True)
                                    os.makedirs("data/transcripts", exist_ok=True)
                                    
                                    with open(f"data/transcripts/{video_id}.txt", "w") as f:
                                        f.write(transcript)
                                    
                                    with open(f"data/summaries/{video_id}.txt", "w") as f:
                                        summary_text = json.dumps(summary, indent=2)
                                        f.write(summary_text)
                                    
                                    st.success(f"💾 Results saved for video ID: `{video_id}`")
                            else:
                                st.error("❌ Failed to generate summary")
                                status.update(label="❌ Summary generation failed", state="error")
                        else:
                            st.error("❌ Could not retrieve transcript")
                            status.update(label="❌ Transcript retrieval failed", state="error")
                            
                            if st.session_state.transcript_error:
                                st.warning(f"Details: {st.session_state.transcript_error}")
                            
                            with st.expander("💡 Troubleshooting Tips"):
                                st.markdown("""
                                **Common issues:**
                                - Video has no captions/subtitles available
                                - Video is private, unlisted, or age-restricted
                                - Video is too new (captions not processed yet)
                                - Regional restrictions
                                
                                **Try:**
                                - Use a popular video with captions
                                - Check if the CC button appears in YouTube player
                                - Copy URL directly from YouTube
                                """)

    with tab2:
        st.header("📺 Channel Management & Automation")
        
        # Backend API endpoint
        backend_url = get_backend_url()
        
        if not backend_url:
            st.warning("⚠️ **Backend Service Required**: Channel management features require a separate backend service.")
            st.markdown("""
            **Missing Backend Features:**
            - Channel tracking and monitoring
            - Automatic daily reports  
            - Scheduled processing
            - Webhook notifications
            
            **To enable these features:**
            1. Deploy the backend service separately
            2. Set `BACKEND_URL` environment variable to point to your backend
            3. Backend handles channel tracking, scheduling, and Discord notifications
            """)
            return
        
        # Get scheduler status
        try:
            scheduler_response = requests.get(f"{backend_url}/api/scheduler/status")
            if scheduler_response.status_code == 200:
                scheduler_data = scheduler_response.json()
                
                # Daily Report Status
                st.subheader("📅 Daily Report Schedule")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Next Report", scheduler_data.get("time_until_next_report", "Unknown"))
                with col2:
                    st.metric("Schedule", scheduler_data.get("report_schedule", "Unknown"))
                with col3:
                    if st.button("� Trigger Now"):
                        # Get webhook token
                        try:
                            token_response = requests.get(f"{backend_url}/api/webhook-token")
                            if token_response.status_code == 200:
                                token = token_response.json()["token"]
                                report_response = requests.post(f"{backend_url}/api/webhook/trigger-daily-report", 
                                                              headers={"Authorization": f"Bearer {token}"})
                                if report_response.status_code == 200:
                                    st.success("Daily report triggered successfully!")
                                else:
                                    st.error("Failed to trigger daily report")
                            else:
                                st.error("Failed to get authentication token")
                        except Exception as e:
                            st.error(f"Error triggering report: {str(e)}")
            else:
                st.warning("Could not load scheduler status")
        except Exception as e:
            st.warning(f"Scheduler status unavailable: {str(e)}")
        
        st.divider()
        
        # Get detailed channel status
        try:
            status_response = requests.get(f"{backend_url}/api/channels/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                # Summary metrics
                st.subheader("📊 Channel Status Overview")
                col1, col2, col3, col4 = st.columns(4)
                summary = status_data.get("summary", {})
                with col1:
                    st.metric("Total Channels", status_data.get("total_channels", 0))
                with col2:
                    st.metric("Up to Date", summary.get("active", 0), delta=None)
                with col3:
                    new_content = summary.get("new_content", 0)
                    st.metric("New Content", new_content, delta=f"+{new_content}" if new_content > 0 else None)
                with col4:
                    errors = summary.get("errors", 0)
                    st.metric("Errors", errors, delta=f"-{errors}" if errors > 0 else None)
                
                # Global actions
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Check All Channels"):
                        with st.spinner("Checking all channels for new videos..."):
                            try:
                                check_all_response = requests.post(f"{backend_url}/api/channels/check-all")
                                if check_all_response.status_code == 200:
                                    result = check_all_response.json()
                                    st.success(f"Found and processed {result.get('new_videos_count', 0)} new videos")
                                    st.rerun()
                                else:
                                    st.error("Failed to check channels")
                            except Exception as e:
                                st.error(f"Error checking channels: {str(e)}")
                
                st.divider()
                
                # Detailed channel list
                st.subheader("📋 Channel Details")
                
                channels = status_data.get("channels", [])
                if channels:
                    for channel_info in channels:
                        channel = channel_info["channel"]
                        status = channel_info["status"]
                        has_new = channel_info.get("has_new_videos", False)
                        
                        # Status icon and color
                        if status == "up_to_date":
                            status_icon = "✅"
                        elif status == "new_content_available":
                            status_icon = "🆕"
                        elif status == "error":
                            status_icon = "❌"
                        else:
                            status_icon = "⚪"
                        
                        # Create expandable section for each channel
                        with st.expander(f"{status_icon} **{channel}** - {status.replace('_', ' ').title()}", expanded=has_new):
                            col1, col2, col3 = st.columns([2, 2, 1])
                            
                            with col1:
                                # Last known video
                                last_video = channel_info.get("last_known_video", {})
                                if last_video.get("id"):
                                    st.write("**Last Tracked Video:**")
                                    st.write(f"ID: `{last_video['id']}`")
                                    if last_video.get("title"):
                                        st.write(f"Title: {last_video['title'][:50]}...")
                                else:
                                    st.write("**No videos tracked yet**")
                            
                            with col2:
                                # Latest available video
                                latest_video = channel_info.get("latest_available_video")
                                if latest_video:
                                    st.write("**Latest Available Video:**")
                                    st.write(f"[{latest_video['title']}]({latest_video['url']})")
                                    st.write(f"Published: {latest_video['publish_time'][:10]}")
                                    if has_new:
                                        st.success("🆕 New content detected!")
                                else:
                                    st.write("**No recent videos found**")
                            
                            with col3:
                                # Channel actions
                                if st.button(f"Check", key=f"check_{channel}"):
                                    with st.spinner(f"Checking {channel}..."):
                                        try:
                                            check_response = requests.post(f"{backend_url}/api/channels/check/{channel}")
                                            if check_response.status_code == 200:
                                                result = check_response.json()
                                                st.success(f"Checked {channel}")
                                                st.rerun()
                                            else:
                                                st.error(f"Failed to check {channel}")
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                
                                if st.button(f"Remove", key=f"remove_{channel}"):
                                    with st.spinner(f"Removing {channel}..."):
                                        try:
                                            remove_response = requests.delete(f"{backend_url}/api/channels/{channel}")
                                            if remove_response.status_code == 200:
                                                st.success(f"Removed {channel}")
                                                st.rerun()
                                            else:
                                                st.error(f"Failed to remove {channel}")
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                            
                            # Show error details if there's an error
                            if status == "error" and "error" in channel_info:
                                st.error(f"Error: {channel_info['error']}")
                
                else:
                    st.info("No channels being tracked.")
            else:
                st.error("Failed to load channel status")
        except Exception as e:
            st.error(f"Error loading channel status: {str(e)}")
        
        st.divider()
        
        # Add new channel section
        st.subheader("➕ Add New Channel")
        col1, col2 = st.columns([3, 1])
        with col1:
            new_channel = st.text_input(
                "Channel Handle:",
                placeholder="@channelname",
                help="Enter the YouTube channel handle starting with @"
            )
        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button("Add Channel", type="primary"):
                if new_channel:
                    if not new_channel.startswith("@"):
                        st.error("Channel handle must start with @")
                    else:
                        with st.spinner(f"Adding {new_channel}..."):
                            try:
                                add_response = requests.post(f"{backend_url}/api/channels/add", json={"channel": new_channel})
                                if add_response.status_code == 200:
                                    result = add_response.json()
                                    st.success(f"Added {new_channel}")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to add channel: {add_response.text}")
                            except Exception as e:
                                st.error(f"Error adding channel: {str(e)}")
                else:
                    st.error("Please enter a channel handle")

    with tab3:
        st.header("🧪 System Testing & Diagnostics")
        
        # System status overview
        st.subheader("🔍 System Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Environment Check**")
            
            # Check environment variables
            env_checks = [
                ("OPENAI_API_KEY", "🔑 OpenAI API Key"),
                ("SUPABASE_URL", "🗄️ Supabase URL"),
                ("SUPABASE_KEY", "🔐 Supabase Key"),
                ("DISCORD_WEBHOOK_UPLOADS", "📤 Discord Uploads"),
                ("DISCORD_WEBHOOK_SUMMARIES", "📋 Discord Summaries"),
                ("DISCORD_WEBHOOK_DAILY_REPORT", "📅 Discord Reports")
            ]
            
            for env_var, display_name in env_checks:
                value = os.getenv(env_var)
                if value:
                    st.success(f"✅ {display_name}")
                else:
                    st.error(f"❌ {display_name}")
        
        with col2:
            st.markdown("**🔗 Service Connectivity**")
            
            # Test backend connection
            if "Online" in backend_status:
                st.success("✅ Backend API")
            else:
                st.error("❌ Backend API")
            
            # Test OpenAI API
            if st.button("🤖 Test OpenAI"):
                openai_key = os.getenv("OPENAI_API_KEY")
                if not openai_key:
                    st.error("❌ OpenAI API key not found")
                else:
                    with st.spinner("Testing OpenAI API..."):
                        try:
                            # Simple test using requests
                            headers = {"Authorization": f"Bearer {openai_key}"}
                            response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
                            if response.status_code == 200:
                                st.success("✅ OpenAI API connection successful")
                            else:
                                st.error(f"❌ OpenAI API error: {response.status_code}")
                        except Exception as e:
                            st.error(f"❌ OpenAI API test failed: {str(e)}")
        
        st.divider()
        
        # Testing tools
        st.subheader("🔧 Testing Tools")
        
        # Video processing test
        st.markdown("**📹 Video Processing Test**")
        test_url = st.text_input(
            "Test YouTube URL:",
            placeholder="https://www.youtube.com/watch?v=...",
            key="test_video_url"
        )
        
        if st.button("🧪 Test Video Processing"):
            if not test_url:
                st.error("❌ Please enter a YouTube URL")
            elif not is_valid_youtube_url(test_url):
                st.error("❌ Invalid YouTube URL format")
            else:
                with st.spinner("🔄 Testing video processing..."):
                    try:
                        # Test transcript retrieval
                        video_id = extract_video_id(test_url)
                        if video_id:
                            st.info(f"📹 Video ID: {video_id}")
                        
                        transcript = asyncio.run(get_cached_transcript(test_url))
                        if transcript:
                            st.success("✅ Transcript retrieval successful")
                            st.info(f"📝 Transcript length: {len(transcript)} characters")
                            
                            # Test summarization if OpenAI key is available
                            openai_key = os.getenv("OPENAI_API_KEY")
                            if openai_key:
                                st.info("🤖 Testing AI summarization...")
                                summary = asyncio.run(chunk_and_summarize(transcript, openai_key))
                                if summary:
                                    st.success("✅ AI summarization successful")
                                    st.json(summary)
                                else:
                                    st.error("❌ AI summarization failed")
                            else:
                                st.warning("⚠️ No OpenAI key for summarization test")
                        else:
                            st.error("❌ Transcript retrieval failed")
                            if st.session_state.transcript_error:
                                st.warning(f"Error: {st.session_state.transcript_error}")
                    except Exception as e:
                        st.error(f"❌ Test failed: {str(e)}")
        
        st.divider()
        
        # Webhook testing
        st.subheader("🔗 Webhook Testing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Discord Webhook Tests**")
            
            # Get webhooks from environment
            uploads_webhook = os.getenv("DISCORD_WEBHOOK_UPLOADS")
            transcripts_webhook = os.getenv("DISCORD_WEBHOOK_TRANSCRIPTS") 
            summaries_webhook = os.getenv("DISCORD_WEBHOOK_SUMMARIES")
            daily_report_webhook = os.getenv("DISCORD_WEBHOOK_DAILY_REPORT")
            
            if uploads_webhook:
                if st.button("🎬 Test Uploads Webhook"):
                    with st.spinner("Testing uploads webhook..."):
                        success, message = asyncio.run(test_uploads_webhook(uploads_webhook))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No uploads webhook configured")
            
            if transcripts_webhook:
                if st.button("📝 Test Transcripts Webhook"):
                    with st.spinner("Testing transcripts webhook..."):
                        success, message = asyncio.run(test_webhook(transcripts_webhook, "transcript"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No transcripts webhook configured")
        
        with col2:
            if summaries_webhook:
                if st.button("📊 Test Summaries Webhook"):
                    with st.spinner("Testing summaries webhook..."):
                        success, message = asyncio.run(test_webhook(summaries_webhook, "summary"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No summaries webhook configured")
            
            if daily_report_webhook:
                if st.button("📅 Test Daily Report Webhook"):
                    with st.spinner("Testing daily report webhook..."):
                        success, message = asyncio.run(test_webhook(daily_report_webhook, "daily_report"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No daily report webhook configured")
        
        st.divider()
        
        # Backend API testing
        st.subheader("🔧 Backend API Testing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Channel Management**")
            test_channel = st.text_input("Test Channel Handle:", placeholder="@channelname", key="test_channel")
            
            if st.button("🧪 Test Channel Videos"):
                if test_channel:
                    if not test_channel.startswith("@"):
                        st.error("Channel handle must start with @")
                    else:
                        with st.spinner(f"Fetching latest videos from {test_channel}..."):
                            try:
                                response = requests.post(f"{backend_url}/api/channels/check/{test_channel}")
                                if response.status_code == 200:
                                    result = response.json()
                                    st.success("Channel check successful!")
                                    st.json(result)
                                else:
                                    st.error(f"Channel check failed: {response.text}")
                            except Exception as e:
                                st.error(f"Error checking channel: {str(e)}")
                else:
                    st.error("Please enter a channel handle")
        
        with col2:
            st.markdown("**Daily Reports**")
            if st.button("📊 Generate Test Daily Report"):
                with st.spinner("Generating daily report..."):
                    try:
                        # Get webhook token first
                        token_response = requests.get(f"{backend_url}/api/webhook-token")
                        if token_response.status_code == 200:
                            token_data = token_response.json()
                            token = token_data.get("token")
                            
                            # Trigger daily report
                            headers = {"Authorization": f"Bearer {token}"}
                            response = requests.post(f"{backend_url}/api/webhook/trigger-daily-report", headers=headers)
                            if response.status_code == 200:
                                result = response.json()
                                st.success("Daily report generated successfully!")
                                st.json(result)
                            else:
                                st.error(f"Daily report failed: {response.text}")
                        else:
                            st.error("Failed to get webhook token")
                    except Exception as e:
                        st.error(f"Error generating daily report: {str(e)}")
        
        st.divider()
        
        # Configuration testing
        st.subheader("⚙️ Configuration Testing")
        
        if st.button("🔍 Test All Configurations"):
            with st.spinner("Testing all configurations..."):
                config_results = {}
                
                # Test OpenAI
                openai_key = os.getenv("OPENAI_API_KEY")
                if openai_key:
                    try:
                        headers = {"Authorization": f"Bearer {openai_key}"}
                        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
                        config_results["OpenAI API"] = "✅ Working" if response.status_code == 200 else f"❌ Error {response.status_code}"
                    except:
                        config_results["OpenAI API"] = "❌ Connection failed"
                else:
                    config_results["OpenAI API"] = "❌ Not configured"
                
                # Test Backend
                try:
                    response = requests.get(f"{backend_url}/api/health", timeout=5)
                    config_results["Backend API"] = "✅ Working" if response.status_code == 200 else f"❌ Error {response.status_code}"
                except:
                    config_results["Backend API"] = "❌ Offline"
                
                # Test webhooks
                webhook_vars = ["DISCORD_WEBHOOK_UPLOADS", "DISCORD_WEBHOOK_TRANSCRIPTS", 
                              "DISCORD_WEBHOOK_SUMMARIES", "DISCORD_WEBHOOK_DAILY_REPORT"]
                
                for var in webhook_vars:
                    webhook_url = os.getenv(var)
                    if webhook_url:
                        config_results[var.replace("DISCORD_WEBHOOK_", "").title()] = "✅ Configured"
                    else:
                        config_results[var.replace("DISCORD_WEBHOOK_", "").title()] = "❌ Not set"
                
                # Display results
                for service, status in config_results.items():
                    if "✅" in status:
                        st.success(f"{service}: {status}")
                    else:
                        st.error(f"{service}: {status}")
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("🤖 **YouTube Summary Bot v2.0**")
    with col2:
        st.caption("🔗 [GitHub Repository](https://github.com/yousuf-fahim/YouTubeSummary)")
    with col3:
        st.caption("📞 [Report Issues](https://github.com/yousuf-fahim/YouTubeSummary/issues)")


if __name__ == "__main__":
    main()
