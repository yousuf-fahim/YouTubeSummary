import streamlit as st
import os
import sys
import re
import asyncio
import json
import time
import requests

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Define default prompts first (ensure they're always available)
DEFAULT_SUMMARY_PROMPT = """You're an advanced content summarizer.
Your task is to analyze the transcript of a YouTube video and return a concise summary in JSON format only.
Include the video's topic, key points, and any noteworthy mentions.
Do not include anything outside of the JSON block. Be accurate, structured, and informative.

Format your response like this:

{
  "title": "Insert video title here",
  "summary": [
    "Key point 1",
    "Key point 2",
    "Key point 3"
  ],
  "noteworthy_mentions": [
    "Person, project, or tool name if mentioned",
    "Important reference or example"
  ],
  "verdict": "Brief 1-line overall takeaway"
}"""

DEFAULT_DAILY_REPORT_PROMPT = """You are an expert content analyst.
Given a list of video summaries from the last 24 hours, your job is to:
Rate each video on a scale from 1 to 10 based on how interesting and watch-worthy it is.
Identify the most engaging topics across all videos.
Highlight 3 key takeaways or trends from these videos.
Write a clear, professional daily report in natural language (no JSON).

Make it easy to read, concise, and useful. Avoid technical jargon.
Output the report as plain text suitable for sharing in a Discord channel."""

# Only load dotenv for local development, not in production
if not hasattr(st, 'secrets') or os.getenv('STREAMLIT_SHARING', 'false').lower() != 'true':
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available in production, that's fine

# Set environment variables from Streamlit secrets before importing shared modules
if hasattr(st, 'secrets'):
    try:
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ[key] = value
        
        if "general" in st.secrets:
            for key, value in st.secrets["general"].items():
                if isinstance(value, str):
                    os.environ[key] = value
    except Exception as e:
        pass

# Try to import shared modules with fallback
try:
    from shared.transcript import get_transcript, extract_video_id
    from shared.summarize import chunk_and_summarize
    try:
        from shared.summarize import DEFAULT_SUMMARY_PROMPT as SHARED_SUMMARY_PROMPT, DEFAULT_DAILY_REPORT_PROMPT as SHARED_DAILY_PROMPT
        DEFAULT_SUMMARY_PROMPT = SHARED_SUMMARY_PROMPT
        DEFAULT_DAILY_REPORT_PROMPT = SHARED_DAILY_PROMPT
    except ImportError:
        pass
    
    from shared.discord_utils import send_discord_message, send_file_to_discord
    from shared.discord_listener import DiscordListener
    from shared.supabase_utils import get_config as get_supabase_config, save_config as save_supabase_config
    from shared.supabase_utils import get_transcript as get_supabase_transcript, get_summary as get_supabase_summary
    from shared.youtube_tracker import get_latest_videos_from_channel, load_tracking_data, save_tracking_data
    SHARED_MODULES_AVAILABLE = True
    IMPORT_STATUS = "✅ SUCCESS: All shared modules imported successfully"
    IMPORT_ERROR = None
except ImportError as e:
    SHARED_MODULES_AVAILABLE = False
    IMPORT_STATUS = "❌ Using API mode due to import error"
    IMPORT_ERROR = f"ImportError: {e}"
    
    # Define fallback functions that use API calls
    def get_transcript(url):
        backend_url = get_backend_url()
        return requests.post(f"{backend_url}/api/transcript", json={"url": url})
        
    def extract_video_id(url):
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

st.set_page_config(page_title="YouTube Summary Bot", page_icon="🤖", layout="wide")

# Set up session state for caching
if "transcripts" not in st.session_state:
    st.session_state.transcripts = {}
    
if "transcript_error" not in st.session_state:
    st.session_state.transcript_error = None

if "show_prompt_editor" not in st.session_state:
    st.session_state.show_prompt_editor = False

def get_backend_url():
    """Get backend URL from environment or secrets"""
    try:
        if hasattr(st, 'secrets') and "BACKEND_URL" in st.secrets:
            return st.secrets["BACKEND_URL"]
        return st.secrets["general"]["backend_url"]
    except:
        pass
    
    backend_url = os.getenv("BACKEND_URL")
    if backend_url:
        return backend_url
    
    return "http://localhost:8001"

def sanitize_filename(title):
    """Convert video title to safe filename"""
    if not title:
        return "unknown_video"
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = sanitized.replace(' ', '_')
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized

def load_config():
    """Load configuration from Supabase or config.json"""
    if SHARED_MODULES_AVAILABLE:
        try:
            supabase_config = get_supabase_config()
            if supabase_config:
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
    
    backend_url = get_backend_url()
    try:
        response = requests.get(f"{backend_url}/api/config")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.warning(f"Could not load config from backend: {e}")
    
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
    saved_somewhere = False
    
    if SHARED_MODULES_AVAILABLE:
        try:
            from shared.supabase_utils import get_supabase_client
            client = get_supabase_client()
            save_supabase_config(config)
            st.success("Configuration saved to Supabase!")
            saved_somewhere = True
        except ValueError as e:
            st.warning(f"Supabase credentials not available: {e}")
        except Exception as e:
            st.warning(f"Could not save config to Supabase: {e}")
    
    backend_url = get_backend_url()
    try:
        response = requests.post(f"{backend_url}/api/config", json=config)
        if response.status_code == 200:
            if not saved_somewhere:
                st.success("Configuration saved via backend API!")
            saved_somewhere = True
        else:
            st.warning("Configuration save may have failed.")
    except Exception as e:
        st.warning(f"Could not save config via API: {e}")
    
    if not saved_somewhere:
        st.error("Failed to save configuration to any storage method!")

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
    
    if video_id and video_id in st.session_state.transcripts:
        return st.session_state.transcripts[video_id]
    
    if video_id:
        supabase_transcript = get_supabase_transcript(video_id)
        if supabase_transcript:
            transcript = supabase_transcript.get("transcript_text")
            st.session_state.transcripts[video_id] = transcript
            return transcript
    
    if video_id:
        transcript_path = f"data/transcripts/{video_id}.txt"
        if os.path.exists(transcript_path):
            with open(transcript_path, 'r') as f:
                transcript = f.read()
                st.session_state.transcripts[video_id] = transcript
                return transcript
    
    st.session_state.transcript_error = None
    
    transcript = await get_transcript(url)
    
    if transcript is None:
        st.session_state.transcript_error = "Could not retrieve transcript"
    
    if transcript and video_id:
        st.session_state.transcripts[video_id] = transcript
        
        os.makedirs("data/transcripts", exist_ok=True)
        with open(f"data/transcripts/{video_id}.txt", 'w') as f:
            f.write(transcript)
    
    return transcript

def test_webhook(webhook_url, message_type="general"):
    """Test a Discord webhook by sending a test message"""
    if not webhook_url:
        return False, "No webhook URL provided"
    
    if not is_valid_discord_webhook(webhook_url):
        return False, "Invalid webhook URL format"
    
    test_msg = {
        "content": f"🧪 **Test Message**\n\nThis is a test of the {message_type} webhook.\n\n✅ Webhook is working correctly!",
        "username": "YouTube Summary Bot",
        "avatar_url": "https://img.icons8.com/color/96/000000/youtube-play.png"
    }
    
    try:
        response = requests.post(webhook_url, json=test_msg, timeout=10)
        if response.status_code in [200, 204]:
            return True, "Test message sent successfully!"
        else:
            return False, f"Webhook test failed: {response.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    st.title("🤖 YouTube Summary Bot")
    
    # Check if environment is properly configured
    backend_url = get_backend_url()
    openai_key = os.getenv("OPENAI_API_KEY")
    
    # Status bar at the top
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if openai_key:
            st.success("🔑 OpenAI Configured")
        else:
            st.error("🔑 OpenAI Missing")
    
    with col2:
        try:
            response = requests.get(f"{backend_url}/health", timeout=5)
            if response.status_code == 200:
                st.success("🔗 Backend Online")
            else:
                st.warning("🔗 Backend Issues")
        except:
            st.error("🔗 Backend Offline")
    
    with col3:
        try:
            scheduler_response = requests.get(f"{backend_url}/api/scheduler/status", timeout=5)
            if scheduler_response.status_code == 200:
                st.success("⏰ Scheduler Active")
            else:
                st.warning("⏰ Scheduler Issues")
        except:
            st.error("⏰ Scheduler Offline")
    
    with col4:
        if st.button("⚙️ Prompt Settings"):
            st.session_state.show_prompt_editor = not st.session_state.show_prompt_editor
    
    # Show prompt editor if toggled
    if st.session_state.show_prompt_editor:
        st.divider()
        with st.expander("🎯 AI Prompt Settings", expanded=True):
            st.info("Customize how the AI generates summaries and daily reports")
            
            config = load_config()
            prompts = config.get("prompts", {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📝 Summary Prompt")
                summary_prompt = st.text_area(
                    "Video Summary Prompt:",
                    value=prompts.get("summary_prompt", DEFAULT_SUMMARY_PROMPT),
                    height=200,
                    help="This prompt determines how individual videos are summarized"
                )
                
                if st.button("🔄 Reset Summary Prompt"):
                    summary_prompt = DEFAULT_SUMMARY_PROMPT
                    st.rerun()
            
            with col2:
                st.subheader("📊 Daily Report Prompt")
                daily_prompt = st.text_area(
                    "Daily Report Prompt:",
                    value=prompts.get("daily_report_prompt", DEFAULT_DAILY_REPORT_PROMPT),
                    height=200,
                    help="This prompt determines how daily reports are generated"
                )
                
                if st.button("🔄 Reset Daily Prompt"):
                    daily_prompt = DEFAULT_DAILY_REPORT_PROMPT
                    st.rerun()
            
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("💾 Save Prompts", type="primary"):
                    current_config = config.copy()
                    if "prompts" not in current_config:
                        current_config["prompts"] = {}
                    current_config["prompts"]["summary_prompt"] = summary_prompt
                    current_config["prompts"]["daily_report_prompt"] = daily_prompt
                    save_config(current_config)
                    st.success("✅ Prompts saved successfully!")
                    
            with col2:
                if st.button("❌ Close Editor"):
                    st.session_state.show_prompt_editor = False
                    st.rerun()
        
        st.divider()
    
    # Main interface tabs
    tab1, tab2, tab3 = st.tabs(["🎬 Video Processor", "📺 Channel Manager", "🧪 System Test"])
    
    with tab1:
        st.header("Process YouTube Videos")
        
        # Quick stats
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
        
        # Automation status section
        st.subheader("🤖 Automation Status")
        
        try:
            scheduler_response = requests.get(f"{backend_url}/api/scheduler/status")
            if scheduler_response.status_code == 200:
                scheduler_data = scheduler_response.json()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📅 Next Report", scheduler_data.get("time_until_next_report", "Unknown"))
                with col2:
                    st.metric("⏰ Schedule", scheduler_data.get("report_schedule", "18:00 CEST"))
                with col3:
                    st.metric("🔄 Auto Check", "Every 30 min", help="Channels are checked automatically")
                with col4:
                    if st.button("🚀 Manual Report"):
                        try:
                            token_response = requests.get(f"{backend_url}/api/webhook-token")
                            if token_response.status_code == 200:
                                token = token_response.json()["token"]
                                report_response = requests.post(f"{backend_url}/api/webhook/trigger-daily-report", 
                                                              headers={"Authorization": f"Bearer {token}"})
                                if report_response.status_code == 200:
                                    st.success("📊 Daily report triggered!")
                                else:
                                    st.error("❌ Failed to trigger report")
                            else:
                                st.error("❌ Authentication failed")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Scheduler status unavailable")
                st.info("💡 The automation system may be starting up or experiencing issues.")
        except Exception as e:
            st.error(f"❌ Cannot connect to scheduler: {str(e)}")
        
        st.divider()
        
        # Channel management section
        st.subheader("📋 Tracked Channels")
        
        # Get channel status
        try:
            status_response = requests.get(f"{backend_url}/api/channels/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                # Overview metrics
                summary = status_data.get("summary", {})
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📺 Total Channels", status_data.get("total_channels", 0))
                with col2:
                    active_count = summary.get("active", 0)
                    st.metric("✅ Up to Date", active_count)
                with col3:
                    new_count = summary.get("new_content", 0)
                    st.metric("🆕 New Content", new_count, delta=f"+{new_count}" if new_count > 0 else None)
                with col4:
                    error_count = summary.get("errors", 0)
                    st.metric("❌ Errors", error_count, delta=f"-{error_count}" if error_count > 0 else None)
                
                # Global actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🔄 Check All Channels", type="primary"):
                        with st.spinner("🔍 Checking all channels for new videos..."):
                            try:
                                check_response = requests.post(f"{backend_url}/api/channels/check-all")
                                if check_response.status_code == 200:
                                    result = check_response.json()
                                    new_videos = result.get('new_videos_count', 0)
                                    if new_videos > 0:
                                        st.success(f"🎉 Found and processed {new_videos} new videos!")
                                    else:
                                        st.info("✅ All channels are up to date")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to check channels")
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                
                with col2:
                    if st.button("📊 Generate Report"):
                        try:
                            token_response = requests.get(f"{backend_url}/api/webhook-token")
                            if token_response.status_code == 200:
                                token = token_response.json()["token"]
                                report_response = requests.post(f"{backend_url}/api/webhook/trigger-daily-report", 
                                                              headers={"Authorization": f"Bearer {token}"})
                                if report_response.status_code == 200:
                                    st.success("📈 Report generated and sent!")
                                else:
                                    st.error("❌ Failed to generate report")
                            else:
                                st.error("❌ Authentication failed")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                
                with col3:
                    if st.button("🔄 Refresh Status"):
                        st.rerun()
                
                st.divider()
                
                # Channel list with improved interface
                channels = status_data.get("channels", [])
                if channels:
                    for i, channel_info in enumerate(channels):
                        channel = channel_info["channel"]
                        status = channel_info["status"]
                        has_new = channel_info.get("has_new_videos", False)
                        
                        # Status styling
                        if status == "up_to_date":
                            status_color = "🟢"
                            status_text = "Up to Date"
                        elif status == "new_content_available":
                            status_color = "🟡"
                            status_text = "New Content Available"
                        elif status == "error":
                            status_color = "🔴"
                            status_text = "Error"
                        else:
                            status_color = "⚪"
                            status_text = "Unknown"
                        
                        # Channel container
                        with st.container():
                            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                            
                            with col1:
                                st.markdown(f"### {status_color} **{channel}**")
                                st.caption(f"Status: {status_text}")
                            
                            with col2:
                                last_video = channel_info.get("last_known_video", {})
                                if last_video.get("title"):
                                    st.markdown("**Last Tracked:**")
                                    st.caption(f"🎬 {last_video['title'][:50]}...")
                                else:
                                    st.caption("No videos tracked yet")
                            
                            with col3:
                                latest_video = channel_info.get("latest_available_video")
                                if latest_video:
                                    st.markdown("**Latest Available:**")
                                    st.markdown(f"🔗 [{latest_video['title'][:30]}...]({latest_video['url']})")
                                    if has_new:
                                        st.success("🆕 Ready to process!")
                                else:
                                    st.caption("No recent videos found")
                            
                            with col4:
                                # Channel actions in a more compact layout
                                if st.button("🔍", key=f"check_{i}", help="Check for new videos"):
                                    with st.spinner(f"Checking {channel}..."):
                                        try:
                                            check_response = requests.post(f"{backend_url}/api/channels/check", 
                                                                         json={"channel": channel})
                                            if check_response.status_code == 200:
                                                result = check_response.json()
                                                if result.get("new_videos_found", 0) > 0:
                                                    st.success(f"✅ Found {result['new_videos_found']} new videos!")
                                                else:
                                                    st.info("✅ No new videos")
                                                st.rerun()
                                            else:
                                                st.error("❌ Check failed")
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                                
                                if st.button("🗑️", key=f"remove_{i}", help="Remove channel"):
                                    if st.session_state.get(f"confirm_remove_{i}", False):
                                        # Actually remove the channel
                                        try:
                                            remove_response = requests.delete(f"{backend_url}/api/channels/remove", 
                                                                           json={"channel": channel})
                                            if remove_response.status_code == 200:
                                                st.success(f"✅ Removed {channel}")
                                                st.rerun()
                                            else:
                                                st.error("❌ Failed to remove channel")
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                                        st.session_state[f"confirm_remove_{i}"] = False
                                    else:
                                        # Ask for confirmation
                                        st.session_state[f"confirm_remove_{i}"] = True
                                        st.warning("Click again to confirm removal")
                            
                            # Show errors if any
                            if status == "error" and "error" in channel_info:
                                st.error(f"🚨 Error: {channel_info['error']}")
                            
                            st.divider()
                
                else:
                    st.info("📭 No channels are currently being tracked")
                    st.markdown("""
                    **Get started:**
                    1. Add a YouTube channel using the form below
                    2. The system will automatically check for new videos every 30 minutes
                    3. New videos will be processed and summarized automatically
                    4. Daily reports will be generated at 18:00 CEST
                    """)
            
            else:
                st.error("❌ Failed to load channel status")
                
        except Exception as e:
            st.error(f"❌ Error loading channels: {str(e)}")
        
        st.divider()
        
        # Add new channel section
        st.subheader("➕ Add New Channel")
        st.info("💡 Enter a YouTube channel handle (starts with @) to begin automatic tracking")
        
        col1, col2 = st.columns([4, 1])
        with col1:
            new_channel = st.text_input(
                "Channel Handle:",
                placeholder="@channelname",
                help="Enter the YouTube channel handle starting with @",
                key="new_channel_input"
            )
        with col2:
            st.write("")  # Spacing
            st.write("")  # Spacing
            add_button = st.button("➕ Add Channel", type="primary")
        
        if add_button:
            if not new_channel:
                st.error("❌ Please enter a channel handle")
            elif not new_channel.startswith("@"):
                st.error("❌ Channel handle must start with @")
            else:
                with st.spinner(f"🔍 Adding {new_channel}..."):
                    try:
                        add_response = requests.post(f"{backend_url}/api/channels/add", 
                                                   json={"channel": new_channel})
                        if add_response.status_code == 200:
                            result = add_response.json()
                            st.success(f"✅ Successfully added {new_channel}!")
                            if result.get("initial_videos_found", 0) > 0:
                                st.info(f"🎬 Found {result['initial_videos_found']} existing videos")
                            st.session_state.new_channel_input = ""  # Clear input
                            st.rerun()
                        else:
                            error_msg = add_response.json().get("detail", "Unknown error")
                            st.error(f"❌ Failed to add channel: {error_msg}")
                    except Exception as e:
                        st.error(f"❌ Error adding channel: {str(e)}")

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
            try:
                response = requests.get(f"{backend_url}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ Backend API")
                else:
                    st.error("❌ Backend API")
            except:
                st.error("❌ Backend API (Unreachable)")
            
            # Test Supabase connection
            if st.button("🗄️ Test Supabase"):
                with st.spinner("Testing Supabase connection..."):
                    try:
                        if SHARED_MODULES_AVAILABLE:
                            from shared.supabase_utils import get_supabase_client
                            client = get_supabase_client()
                            response = client.table('config').select('*').limit(1).execute()
                            st.success("✅ Supabase connection successful")
                        else:
                            st.warning("⚠️ Shared modules not available for direct testing")
                    except Exception as e:
                        st.error(f"❌ Supabase connection failed: {str(e)}")
            
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
        
        # Debug information
        with st.expander("🔧 Debug Information"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Import Status:**")
                st.write(f"- Shared modules: {SHARED_MODULES_AVAILABLE}")
                st.write(f"- Status: {IMPORT_STATUS}")
                if IMPORT_ERROR:
                    st.error(f"Import error: {IMPORT_ERROR}")
                
                st.markdown("**Backend Configuration:**")
                st.write(f"- Backend URL: {backend_url}")
                st.write(f"- ENV BACKEND_URL: {os.getenv('BACKEND_URL', 'Not set')}")
            
            with col2:
                st.markdown("**Module Information:**")
                modules_info = {
                    "requests": "✅" if "requests" in sys.modules else "❌",
                    "streamlit": "✅" if "streamlit" in sys.modules else "❌",
                    "asyncio": "✅" if "asyncio" in sys.modules else "❌",
                    "json": "✅" if "json" in sys.modules else "❌"
                }
                
                for module, status in modules_info.items():
                    st.write(f"- {module}: {status}")
        
        st.divider()
        
        # Testing tools
        st.subheader("🔧 Testing Tools")
        
        # Video processing test
        col1, col2 = st.columns(2)
        
        with col1:
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
        
        with col2:
            st.markdown("**🎯 Channel Test**")
            test_channel = st.text_input(
                "Test Channel Handle:",
                placeholder="@channelname",
                key="test_channel_handle"
            )
            
            if st.button("🧪 Test Channel Fetch"):
                if not test_channel:
                    st.error("❌ Please enter a channel handle")
                elif not test_channel.startswith("@"):
                    st.error("❌ Channel handle must start with @")
                else:
                    with st.spinner(f"🔄 Testing channel: {test_channel}..."):
                        try:
                            # Test via backend API
                            response = requests.get(f"{backend_url}/api/channels/test", 
                                                  params={"channel": test_channel})
                            if response.status_code == 200:
                                data = response.json()
                                st.success("✅ Channel fetch successful")
                                st.info(f"📺 Channel: {data.get('channel_name', 'Unknown')}")
                                st.info(f"🎬 Videos found: {data.get('video_count', 0)}")
                                
                                if data.get('latest_video'):
                                    latest = data['latest_video']
                                    st.info(f"🔗 Latest: [{latest.get('title', 'No title')}]({latest.get('url', '#')})")
                            else:
                                error_msg = response.json().get("detail", "Unknown error")
                                st.error(f"❌ Channel test failed: {error_msg}")
                        except Exception as e:
                            st.error(f"❌ Test failed: {str(e)}")
        
        st.divider()
        
        # Manual triggers for testing
        st.subheader("🎮 Manual Triggers")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Test Daily Report"):
                with st.spinner("🔄 Generating test daily report..."):
                    try:
                        token_response = requests.get(f"{backend_url}/api/webhook-token")
                        if token_response.status_code == 200:
                            token = token_response.json()["token"]
                            report_response = requests.post(f"{backend_url}/api/webhook/trigger-daily-report", 
                                                          headers={"Authorization": f"Bearer {token}"})
                            if report_response.status_code == 200:
                                st.success("✅ Daily report triggered successfully!")
                            else:
                                st.error("❌ Failed to trigger daily report")
                        else:
                            st.error("❌ Failed to get authentication token")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        with col2:
            if st.button("🔄 Test Channel Check"):
                with st.spinner("🔄 Testing channel check system..."):
                    try:
                        response = requests.post(f"{backend_url}/api/channels/check-all")
                        if response.status_code == 200:
                            result = response.json()
                            new_videos = result.get('new_videos_count', 0)
                            st.success(f"✅ Channel check complete! Found {new_videos} new videos")
                        else:
                            st.error("❌ Channel check failed")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        with col3:
            if st.button("🧹 Clear Cache"):
                try:
                    # Clear session state caches
                    if "transcripts" in st.session_state:
                        st.session_state.transcripts = {}
                    if "transcript_error" in st.session_state:
                        st.session_state.transcript_error = None
                    
                    st.success("✅ Cache cleared successfully!")
                except Exception as e:
                    st.error(f"❌ Error clearing cache: {str(e)}")
        
        # Webhook testing
        st.divider()
        st.subheader("📡 Webhook Testing")
        
        webhook_types = [
            ("DISCORD_WEBHOOK_UPLOADS", "📤 Uploads Webhook"),
            ("DISCORD_WEBHOOK_SUMMARIES", "📋 Summaries Webhook"), 
            ("DISCORD_WEBHOOK_DAILY_REPORT", "📅 Daily Report Webhook")
        ]
        
        for env_var, display_name in webhook_types:
            webhook_url = os.getenv(env_var)
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if webhook_url:
                    st.success(f"✅ {display_name} configured")
                else:
                    st.error(f"❌ {display_name} not configured")
            
            with col2:
                if webhook_url and st.button("🧪 Test", key=f"test_{env_var}"):
                    with st.spinner(f"Testing {display_name}..."):
                        try:
                            success, message = test_webhook(webhook_url, message_type=env_var.split('_')[-1].lower())
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"❌ Test failed: {str(e)}")


if __name__ == "__main__":
    main()
