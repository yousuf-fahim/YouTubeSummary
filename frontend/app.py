import streamlit as st
import os
import sys
import re

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import json
import time
import requests

# Only load dotenv for local development, not in production
if not hasattr(st, 'secrets') or os.getenv('STREAMLIT_SHARING', 'false').lower() != 'true':
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv not available in production, that's fine

def get_backend_url():
    """Get backend URL from environment or secrets"""
    # Try Streamlit secrets first (for production)
    try:
        # Try direct access first
        if hasattr(st, 'secrets') and "BACKEND_URL" in st.secrets:
            return st.secrets["BACKEND_URL"]
        # Try nested access
        return st.secrets["general"]["backend_url"]
    except:
        pass
    
    # Try environment variable
    backend_url = os.getenv("BACKEND_URL")
    if backend_url:
        return backend_url
    
    # Default to localhost for development
    return "http://localhost:8001"

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

st.set_page_config(page_title="YouTube Summary", page_icon="📝", layout="wide")

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
    import ssl
    
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
    st.title("YouTube Summary Tool")
    
    # Load config
    config = load_config()
    api_key = config.get("openai_api_key", "")
    
    # Sidebar for status and recent videos
    with st.sidebar:
        st.header("Status")
        
        # Check Discord bot status
        bot_status = check_discord_bot_status()
        if bot_status:
            st.success("Discord bot: Online")
        else:
            st.error("Discord bot: Offline")
        
        # Check OpenAI API key status
        if api_key:
            st.success("OpenAI API key: Configured")
        else:
            st.error("OpenAI API key: Not configured")
        
        # About section
        st.header("About")
        st.write("""
        This tool allows you to get AI-generated summaries of YouTube videos.
        Simply paste a YouTube URL to get started.
        """)
        
        # Troubleshooting expander
        with st.expander("Troubleshooting Tips"):
            st.markdown("""
            ### If transcript retrieval fails:
            
            1. **Check if the video has captions/subtitles**
               - Some videos don't have any captions available
               
            2. **Check if the video is private or restricted**
               - Private videos can't be processed
               
            3. **Try a different video**
               - Use a popular video to test the system
               
            4. **Copy the URL directly from YouTube**
               - Make sure the video ID is correct
        """)
    
    # Tabs for different functionality
    tab1, tab2, tab3, tab4 = st.tabs(["YouTube Summary", "Configuration", "Channel Tracking", "Testing"])
    
    with tab1:
        st.header("Generate YouTube Summary")
        
        # Input for YouTube URL
        youtube_url = st.text_input("Enter YouTube URL:", placeholder="https://www.youtube.com/watch?v=...", key="youtube_url_tab1")
        
        if youtube_url:
            # Validate YouTube URL
            if not is_valid_youtube_url(youtube_url):
                st.error("Invalid YouTube URL format. Please enter a valid URL.")
                
                # Check if it looks like a video ID rather than a URL
                if len(youtube_url) == 11 and re.match(r'^[A-Za-z0-9_-]{11}$', youtube_url):
                    st.info(f"It looks like you entered just a video ID. Try using the full URL: https://www.youtube.com/watch?v={youtube_url}")
            else:
                # Check if API key is configured
                if not api_key:
                    st.error("Please configure your OpenAI API key in the Configuration tab first.")
                else:
                    with st.spinner("Getting transcript..."):
                        # Show progress
                        progress_bar = st.progress(0)
                        progress_bar.progress(25)
                        
                        # Extract video ID for information
                        video_id = extract_video_id(youtube_url)
                        if video_id:
                            st.info(f"Processing video ID: {video_id}")
                        
                        # Get transcript with caching
                        transcript = asyncio.run(get_cached_transcript(youtube_url))
                        progress_bar.progress(100)
                        
                        if transcript:
                            st.success("Transcript retrieved successfully!")
                            
                            with st.expander("View Transcript", expanded=False):
                                st.text_area("Full Transcript", transcript, height=300)
                            
                            # Generate summary button
                            if st.button("Generate Summary"):
                                try:
                                    with st.spinner("Generating summary... This may take a minute for longer videos."):
                                        # Show progress during summary generation
                                        progress_bar = st.progress(0)
                                        
                                        # Generate summary with progress updates
                                        for i in range(10):
                                            progress_bar.progress(i * 10)
                                            time.sleep(0.2)  # Small delay for visual feedback
                                            
                                        summary = asyncio.run(chunk_and_summarize(transcript, api_key))
                                        progress_bar.progress(100)
                                        
                                        if summary:
                                            st.subheader(summary.get("title", "Summary"))
                                            
                                            # Display key points
                                            st.subheader("Key Points")
                                            for point in summary.get("points", []):
                                                st.markdown(f"- {point}")
                                            
                                            # Display noteworthy mentions if present
                                            if summary.get("noteworthy_mentions") and len(summary.get("noteworthy_mentions")) > 0:
                                                st.subheader("Noteworthy Mentions")
                                                for mention in summary.get("noteworthy_mentions"):
                                                    st.markdown(f"- {mention}")
                                            
                                            # Display verdict if present
                                            if summary.get("verdict"):
                                                st.subheader("Verdict")
                                                st.markdown(summary.get("verdict"))
                                            
                                            # Display summary text
                                            st.subheader("Summary")
                                            st.markdown(summary.get("summary", "No summary generated"))
                                            
                                            # Save option
                                            if st.button("Save Summary"):
                                                # Create directories if they don't exist
                                                os.makedirs("data/summaries", exist_ok=True)
                                                os.makedirs("data/transcripts", exist_ok=True)
                                                
                                                # Extract video ID from URL
                                                video_id = extract_video_id(youtube_url)
                                                
                                                if video_id:
                                                    # Save transcript
                                                    with open(f"data/transcripts/{video_id}.txt", "w") as f:
                                                        f.write(transcript)
                                                        
                                                    # Save summary
                                                    with open(f"data/summaries/{video_id}.txt", "w") as f:
                                                        f.write(f"Title: {summary.get('title', 'Summary')}\n\n")
                                                        
                                                        if summary.get("verdict"):
                                                            f.write(f"Verdict: {summary.get('verdict')}\n\n")
                                                            
                                                        f.write("Key Points:\n")
                                                        for point in summary.get("points", []):
                                                            f.write(f"- {point}\n")
                                                        
                                                        if summary.get("noteworthy_mentions") and len(summary.get("noteworthy_mentions")) > 0:
                                                            f.write("\nNoteworthy Mentions:\n")
                                                            for mention in summary.get("noteworthy_mentions"):
                                                                f.write(f"- {mention}\n")
                                                            
                                                        f.write("\nSummary:\n")
                                                        f.write(summary.get("summary", "No summary generated"))
                                                        
                                                    st.success(f"Summary and transcript saved for video ID: {video_id}")
                                        else:
                                            st.error("Failed to generate summary. Please try again.")
                                            if st.button("Retry"):
                                                st.rerun()
                                except Exception as e:
                                    st.error(f"Error generating summary: {str(e)}")
                                    if st.button("Retry"):
                                        st.rerun()
                        else:
                            st.error("Could not retrieve transcript for this video. Please check the URL and try again.")
                            
                            # Show more details
                            if st.session_state.transcript_error:
                                st.warning("Detailed error: " + st.session_state.transcript_error)
                                
                            # Provide suggestions
                            with st.expander("Possible Solutions"):
                                st.markdown("""
                                ### Why might transcript retrieval fail:
                                
                                1. **The video doesn't have any captions or subtitles**
                                   - Many videos, especially older ones, don't have captions
                                
                                2. **The video is private, unlisted, or age-restricted**
                                   - Private content can't be accessed by our tools
                                
                                3. **The video ID might be incorrect**
                                   - Double-check the URL from YouTube
                                
                                ### What to try:
                                
                                - Try another popular YouTube video that likely has captions
                                - Make sure you're copying the URL directly from YouTube
                                - Check if the video has captions by looking for the CC button in the YouTube player
                                """)
                                
                                st.subheader("Try a sample video")
                                if st.button("Use Sample Video"):
                                    # Rick Astley's "Never Gonna Give You Up" has captions
                                    st.session_state.sample_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                                    st.rerun()
    
    with tab2:
        st.header("Configuration")
        
        # Use tabs for different configuration sections
        config_tabs = st.tabs(["API Keys", "Webhooks", "Prompts"])
        
        with config_tabs[0]:
            st.subheader("OpenAI API Key")
            
            # OpenAI API Key Configuration
            api_key_input = st.text_input("OpenAI API Key:", value=api_key, type="password",
                                        help="Your OpenAI API key is required for generating summaries.")
            
            # Test API key button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Test API Key"):
                    if not api_key_input:
                        st.error("Please enter an API key first.")
                    else:
                        with st.spinner("Testing API key..."):
                            if test_openai_api_key(api_key_input):
                                st.success("API key is valid!")
                            else:
                                st.error("API key is invalid or has insufficient permissions")
            
            with col2:
                # Save button for this section
                if st.button("Save API Key"):
                    current_config = config.copy()
                    current_config["openai_api_key"] = api_key_input
                    save_config(current_config)
                    st.success("API key saved successfully!")
                    
                    # Offer to restart the app if API key changed
                    if api_key_input != api_key:
                        st.warning("You've changed the API key. The application may need to be restarted for changes to take full effect.")
        
        with config_tabs[1]:
            st.subheader("Discord Webhooks")
            st.info("Configure Discord webhook URLs for notifications.")
            
            # Discord Webhook Configuration
            webhooks = config.get("webhooks", {})
            
            uploads_webhook = st.text_input("YouTube Uploads Webhook:", 
                                        value=webhooks.get("yt_uploads", ""),
                                        help="Discord webhook URL for YouTube upload notifications.")
            
            transcripts_webhook = st.text_input("Transcripts Webhook:", 
                                            value=webhooks.get("yt_transcripts", ""),
                                            help="Discord webhook URL for transcript notifications.")
            
            summaries_webhook = st.text_input("Summaries Webhook:", 
                                            value=webhooks.get("yt_summaries", ""),
                                            help="Discord webhook URL for summary notifications.")
            
            daily_report_webhook = st.text_input("Daily Report Webhook:", 
                                            value=webhooks.get("daily_report", ""),
                                            help="Discord webhook URL for daily report notifications.")
            
            # Save button for webhooks section
            if st.button("Save Webhooks"):
                current_config = config.copy()
                current_config["webhooks"] = {
                    "yt_uploads": uploads_webhook,
                    "yt_transcripts": transcripts_webhook,
                    "yt_summaries": summaries_webhook,
                    "daily_report": daily_report_webhook
                }
                save_config(current_config)
                st.success("Webhooks saved successfully!")
        
        with config_tabs[2]:
            st.subheader("AI Prompts")
            st.info("Customize the prompts used for generating summaries and daily reports.")
            
            # Get current prompt values
            prompts = config.get("prompts", {})
            summary_prompt = prompts.get("summary_prompt", DEFAULT_SUMMARY_PROMPT)
            daily_report_prompt = prompts.get("daily_report_prompt", DEFAULT_DAILY_REPORT_PROMPT)
            
            # Summary prompt
            st.write("**Summary Prompt**")
            st.write("This prompt is used to generate summaries for individual videos.")
            summary_prompt_input = st.text_area("Summary Prompt:", value=summary_prompt, height=200)
            
            # Add a reset button for summary prompt
            if st.button("Reset to Default Summary Prompt"):
                summary_prompt_input = DEFAULT_SUMMARY_PROMPT
                st.session_state.summary_prompt_reset = True
                st.rerun()
            
            st.write("**Daily Report Prompt**")
            st.write("This prompt is used to generate daily reports from multiple video summaries.")
            daily_report_prompt_input = st.text_area("Daily Report Prompt:", value=daily_report_prompt, height=200)
            
            # Add a reset button for daily report prompt
            if st.button("Reset to Default Daily Report Prompt"):
                daily_report_prompt_input = DEFAULT_DAILY_REPORT_PROMPT
                st.session_state.daily_report_prompt_reset = True
                st.rerun()
            
            # Save button for prompts
            if st.button("Save Prompts"):
                current_config = config.copy()
                if "prompts" not in current_config:
                    current_config["prompts"] = {}
                    
                current_config["prompts"]["summary_prompt"] = summary_prompt_input
                current_config["prompts"]["daily_report_prompt"] = daily_report_prompt_input
                
                save_config(current_config)
                st.success("Prompts saved successfully!")
    
    with tab3:
        st.header("📺 Channel Tracking")
        st.info("Track YouTube channels to automatically process their latest videos.")
        
        # Backend API endpoint
        backend_url = get_backend_url()
        
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
                    if st.button("🚀 Trigger Now"):
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
                            status_color = "green"
                        elif status == "new_content_available":
                            status_icon = "🆕"
                            status_color = "orange"
                        elif status == "error":
                            status_icon = "❌"
                            status_color = "red"
                        else:
                            status_icon = "⚪"
                            status_color = "gray"
                        
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
                                        st.write(f"Title: {last_video['title']}")
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
                                                st.success("Check completed!")
                                                st.rerun()
                                            else:
                                                st.error("Check failed")
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
                                                st.error("Removal failed")
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
                    for channel in channels:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.write(f"**{channel}**")
                        with col2:
                            if st.button(f"Check {channel}", key=f"check_{channel}"):
                                with st.spinner(f"Checking {channel} for new videos..."):
                                    try:
                                        check_response = requests.post(f"{backend_url}/api/channels/check/{channel}")
                                        if check_response.status_code == 200:
                                            result = check_response.json()
                                            st.success(f"Check completed: {result.get('message', 'Success')}")
                                        else:
                                            st.error(f"Failed to check channel: {check_response.text}")
                                    except Exception as e:
                                        st.error(f"Error checking channel: {str(e)}")

    with tab4:
        st.header("Testing")
        st.info("Test different components of the application.")
        
        # Backend API endpoint
        backend_url = get_backend_url()
        
        # Video processing test
        st.subheader("Video Processing Test")
        test_url = st.text_input("Test YouTube URL:", placeholder="https://www.youtube.com/watch?v=...", key="test_url")
        
        if st.button("Test Video Processing"):
            if test_url:
                with st.spinner("Testing video processing pipeline..."):
                    try:
                        response = requests.post(f"{backend_url}/api/test", json={"youtube_url": test_url})
                        if response.status_code == 200:
                            result = response.json()
                            st.success("Pipeline test successful!")
                            st.json(result)
                        else:
                            st.error(f"Pipeline test failed: {response.text}")
                    except Exception as e:
                        st.error(f"Error testing pipeline: {str(e)}")
            else:
                st.error("Please enter a YouTube URL")
        
        # Channel video fetching test
        st.subheader("Channel Video Fetching Test")
        test_channel = st.text_input("Test Channel Handle:", placeholder="@channelname", key="test_channel")
        
        if st.button("Test Channel Videos"):
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
        
        # Daily report test
        st.subheader("Daily Report Test")
        if st.button("Generate Daily Report"):
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
        
        # Webhook testing
        st.subheader("Webhook Testing")
        webhooks = config.get("webhooks", {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Summary Webhook**")
            if webhooks.get("yt_summaries"):
                if st.button("Test Summary Webhook"):
                    with st.spinner("Testing summary webhook..."):
                        success, message = asyncio.run(test_webhook(webhooks["yt_summaries"], "summary"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No summary webhook configured")
        
        with col2:
            st.write("**Daily Report Webhook**")
            if webhooks.get("daily_report"):
                if st.button("Test Daily Report Webhook"):
                    with st.spinner("Testing daily report webhook..."):
                        success, message = asyncio.run(test_webhook(webhooks["daily_report"], "daily_report"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            else:
                st.warning("No daily report webhook configured")

if __name__ == "__main__":
    # If sample URL was set from troubleshooting section
    if 'sample_url' in st.session_state:
        st.text_input("Enter YouTube URL:", value=st.session_state.sample_url, key="youtube_url")
        # Remove it after use
        del st.session_state.sample_url
    
    # Handle prompt resets from session state
    if hasattr(st.session_state, 'summary_prompt_reset') and st.session_state.summary_prompt_reset:
        config = load_config()
        if "prompts" not in config:
            config["prompts"] = {}
        config["prompts"]["summary_prompt"] = DEFAULT_SUMMARY_PROMPT
        save_config(config)
        del st.session_state.summary_prompt_reset
    
    if hasattr(st.session_state, 'daily_report_prompt_reset') and st.session_state.daily_report_prompt_reset:
        config = load_config()
        if "prompts" not in config:
            config["prompts"] = {}
        config["prompts"]["daily_report_prompt"] = DEFAULT_DAILY_REPORT_PROMPT
        save_config(config)
        del st.session_state.daily_report_prompt_reset
        
    main() 