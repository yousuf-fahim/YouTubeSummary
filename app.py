import streamlit as st
import os
import sys
import asyncio
import json
import re
import time
import requests
from transcript import get_transcript, extract_video_id
from summarize import chunk_and_summarize, DEFAULT_SUMMARY_PROMPT, DEFAULT_DAILY_REPORT_PROMPT
from discord_utils import send_discord_message, send_file_to_discord
from discord_listener import DiscordListener
from supabase_utils import get_config as get_supabase_config, save_config as save_supabase_config
from supabase_utils import get_transcript as get_supabase_transcript, get_summary as get_supabase_summary

st.set_page_config(page_title="YouTube Summary", page_icon="📝", layout="wide")

# Set up session state for caching
if "transcripts" not in st.session_state:
    st.session_state.transcripts = {}
    
# Store transcript error messages
if "transcript_error" not in st.session_state:
    st.session_state.transcript_error = None

def load_config():
    """Load configuration from Supabase or config.json"""
    # Try to get config from Supabase first
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
    
    # Fall back to local file if Supabase config not available
    config_path = os.path.join("data", "config.json")
    
    if not os.path.exists(config_path):
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
    
    with open(config_path, "r") as f:
        try:
            config = json.load(f)
            # Make sure prompts section exists
            if "prompts" not in config:
                config["prompts"] = {
                    "summary_prompt": DEFAULT_SUMMARY_PROMPT,
                    "daily_report_prompt": DEFAULT_DAILY_REPORT_PROMPT
                }
            # Make sure webhook_auth_token exists
            if "webhook_auth_token" not in config:
                config["webhook_auth_token"] = ""
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
                    "summary_prompt": DEFAULT_SUMMARY_PROMPT,
                    "daily_report_prompt": DEFAULT_DAILY_REPORT_PROMPT
                },
                "webhook_auth_token": ""
            }

def save_config(config):
    """Save configuration to Supabase and local config.json"""
    # Save to Supabase
    save_supabase_config(config)
    
    # Also save locally as backup
    os.makedirs("data", exist_ok=True)
    config_path = os.path.join("data", "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

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
    tab1, tab2, tab3, tab4 = st.tabs(["YouTube Summary", "Configuration", "Discord Testing", "Webhook Setup"])
    
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
                                                st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"Error generating summary: {str(e)}")
                                    if st.button("Retry"):
                                        st.experimental_rerun()
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
                                    st.experimental_rerun()
    
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
        if st.button("Test API Key"):
            if not api_key_input:
                st.error("Please enter an API key first.")
            else:
                with st.spinner("Testing API key..."):
                    if test_openai_api_key(api_key_input):
                        st.success("API key is valid!")
                    else:
                        st.error("API key is invalid or has insufficient permissions")
        
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
            st.write("##### Summary Prompt")
            st.write("This prompt is used to generate summaries for individual videos.")
            summary_prompt_input = st.text_area("Summary Prompt:", value=summary_prompt, height=300)
            
            # Add a reset button for summary prompt
            if st.button("Reset to Default Summary Prompt"):
                summary_prompt_input = DEFAULT_SUMMARY_PROMPT
                st.session_state.summary_prompt_reset = True
                st.experimental_rerun()
            
            st.write("##### Daily Report Prompt")
            st.write("This prompt is used to generate daily reports from multiple video summaries.")
            daily_report_prompt_input = st.text_area("Daily Report Prompt:", value=daily_report_prompt, height=300)
            
            # Add a reset button for daily report prompt
            if st.button("Reset to Default Daily Report Prompt"):
                daily_report_prompt_input = DEFAULT_DAILY_REPORT_PROMPT
                st.session_state.daily_report_prompt_reset = True
                st.experimental_rerun()
            
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
        st.header("Discord Webhook Testing")
        st.info("Use this tab to test your Discord webhook integrations.")
        
        # Load webhooks from config
        webhooks = config.get("webhooks", {})
        
        st.subheader("Test Webhooks")
        
        # Create two columns for better layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Transcript Webhook")
            transcript_url = webhooks.get("yt_transcripts", "")
            
            if not transcript_url:
                st.warning("No transcript webhook configured. Set it in the Configuration tab.")
            else:
                if st.button("Test Transcript Webhook"):
                    with st.spinner("Testing transcript webhook..."):
                        success, message = asyncio.run(test_webhook(transcript_url, "transcript"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            
            st.write("##### Summary Webhook")
            summary_url = webhooks.get("yt_summaries", "")
            
            if not summary_url:
                st.warning("No summary webhook configured. Set it in the Configuration tab.")
            else:
                if st.button("Test Summary Webhook"):
                    with st.spinner("Testing summary webhook..."):
                        success, message = asyncio.run(test_webhook(summary_url, "summary"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        
        with col2:
            st.write("##### Daily Report Webhook")
            daily_url = webhooks.get("daily_report", "")
            
            if not daily_url:
                st.warning("No daily report webhook configured. Set it in the Configuration tab.")
            else:
                if st.button("Test Daily Report Webhook"):
                    with st.spinner("Testing daily report webhook..."):
                        success, message = asyncio.run(test_webhook(daily_url, "daily_report"))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            
            st.write("##### YouTube Uploads Webhook")
            uploads_url = webhooks.get("yt_uploads", "")
            
            if not uploads_url:
                st.warning("No YouTube uploads webhook configured. Set it in the Configuration tab.")
            else:
                if st.button("Test YouTube Uploads Webhook"):
                    with st.spinner("Testing YouTube uploads webhook..."):
                        success, message = asyncio.run(test_uploads_webhook(uploads_url))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        
        # NotifyMe Integration
        st.subheader("NotifyMe Bot Integration")
        st.write("Process videos from NotifyMe Discord bot notifications")
        
        # Display example NotifyMe message
        with st.expander("Example NotifyMe Message", expanded=False):
            st.markdown("""
            ```
            NotifyMe APP 21/7/25, 2:51PM
            Iman Gadzhi just posted a new video!
            youtu.be/US47EpxBVHk
            YouTube
            Iman Gadzhi
            Build A One-Person Business As A Beginner (From $0 To $10K)
            ```
            """)
            
            # Add image of NotifyMe message
            st.write("When properly configured, the application will automatically detect and process videos from NotifyMe notifications.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Test NotifyMe Integration"):
                with st.spinner("Processing sample NotifyMe notification... This may take some time."):
                    success, message = asyncio.run(process_notifyme_message())
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        
        with col2:
            # Sample video process button
            if st.button("Process Sample Video"):
                with st.spinner("Processing sample video... This may take some time."):
                    success, message = asyncio.run(process_latest_video())
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                        
    with tab4:
        st.header("Webhook Setup")
        st.write("Configure Discord to forward NotifyMe messages to this application")
        
        # Get the current webhook token
        webhook_token = get_webhook_token()
        
        st.info("""
        ### How to Set Up Discord Webhook Forwarding
        
        To automatically process new videos from NotifyMe:
        
        1. Create a webhook in your Discord server settings
        2. Set the webhook URL to point to your server: `http://your-server-address:8000/api/webhook/notifyme`
        3. Include the authorization token in the webhook headers
        4. Configure NotifyMe to post notifications to the channel with your webhook
        
        The webhook will receive NotifyMe notifications and trigger the processing pipeline automatically.
        """)
        
        # Display webhook URL
        st.subheader("Webhook Endpoint")
        
        # Get server address
        server_address = st.text_input(
            "Server Address:",
            value="http://localhost:8000",
            help="The address where this application is hosted. Use your public IP or domain name for production."
        )
        
        st.code(f"{server_address}/api/webhook/notifyme")
        
        # Display authorization token
        st.subheader("Authorization Token")
        st.write("Include this token in the Authorization header of webhook requests.")
        
        if webhook_token:
            # Show the token with a copy button
            st.code(f"Bearer {webhook_token}")
            
            # Add regenerate button
            if st.button("Regenerate Token"):
                with st.spinner("Regenerating token..."):
                    new_token = regenerate_webhook_token()
                    if new_token:
                        st.success("Token regenerated successfully!")
                        st.code(f"Bearer {new_token}")
                        webhook_token = new_token
                    else:
                        st.error("Failed to regenerate token.")
        else:
            st.warning("No webhook token found. Please restart the application to generate one.")
        
        # Instructions for setting up the webhook in Discord
        st.subheader("Discord Webhook Setup")
        st.markdown("""
        1. Go to your Discord server settings
        2. Select "Integrations" → "Webhooks"
        3. Create a new webhook
        4. Set the name to "NotifyMe Forwarder"
        5. Select the channel where NotifyMe posts notifications
        6. Copy the webhook URL and configure it with a service like [webhook.site](https://webhook.site) to forward to your endpoint
        
        ### Daily Report Timing
        
        The daily report will be automatically generated and sent at 18:00 CEST to the Daily Report webhook channel.
        """)
        
        # Test the webhook endpoint
        st.subheader("Test Webhook Endpoint")
        if st.button("Test Webhook Endpoint"):
            # Try to call the webhook endpoint with a test message
            try:
                headers = {"Authorization": f"Bearer {webhook_token}"}
                payload = {
                    "content": "NotifyMe APP 21/7/25, 2:51PM\nTest User just posted a new video!\nyoutu.be/dQw4w9WgXcQ\nYouTube\nTest User\nTest Video"
                }
                
                with st.spinner("Testing webhook endpoint..."):
                    response = requests.post(f"{server_address}/api/webhook/notifyme", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        st.success("Webhook endpoint test successful!")
                        st.json(response.json())
                    else:
                        st.error(f"Webhook endpoint test failed with status code {response.status_code}")
                        st.text(response.text)
            except Exception as e:
                st.error(f"Error testing webhook endpoint: {str(e)}")

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