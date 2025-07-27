#!/usr/bin/env python3
"""
Specific diagnostics for the reported issues:
1. Transcription problems
2. Channel tracking issues  
3. Discord webhook failures
"""
import os
import sys
import requests
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def test_transcription_detailed():
    """Test transcription with detailed error reporting"""
    print("🎬 DETAILED TRANSCRIPTION TEST")
    print("=" * 50)
    
    try:
        from shared.transcript import get_transcript, extract_video_id
        
        test_videos = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - popular video
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # Me at the zoo - first YouTube video
        ]
        
        for url in test_videos:
            print(f"\n🔍 Testing: {url}")
            video_id = extract_video_id(url)
            print(f"📹 Video ID: {video_id}")
            
            try:
                transcript = await get_transcript(url)
                if transcript:
                    print(f"✅ Transcript retrieved: {len(transcript)} characters")
                    print(f"📝 Preview: {transcript[:100]}...")
                else:
                    print("❌ Transcript retrieval failed")
            except Exception as e:
                print(f"❌ Transcription error: {str(e)}")
                
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ General error: {e}")

def test_youtube_api_directly():
    """Test YouTube transcript API directly"""
    print("\n📺 YOUTUBE TRANSCRIPT API TEST")
    print("=" * 50)
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        video_id = "dQw4w9WgXcQ"
        print(f"Testing video ID: {video_id}")
        
        # Test different methods
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            print(f"✅ Standard method worked: {len(transcript)} segments")
        except Exception as e:
            print(f"❌ Standard method failed: {e}")
            
            try:
                # Try with different language codes
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'auto'])
                print(f"✅ Language fallback worked: {len(transcript)} segments")
            except Exception as e2:
                print(f"❌ Language fallback failed: {e2}")
                
                try:
                    # Try getting available transcripts
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    available = [t.language_code for t in transcript_list]
                    print(f"📋 Available transcripts: {available}")
                except Exception as e3:
                    print(f"❌ Cannot list transcripts: {e3}")
                    
    except ImportError as e:
        print(f"❌ youtube_transcript_api not available: {e}")

def test_discord_webhooks_detailed():
    """Test Discord webhooks with detailed debugging"""
    print("\n📨 DETAILED DISCORD WEBHOOK TEST")
    print("=" * 50)
    
    webhooks = {
        "DISCORD_WEBHOOK_UPLOADS": "Uploads",
        "DISCORD_WEBHOOK_TRANSCRIPTS": "Transcripts", 
        "DISCORD_WEBHOOK_SUMMARIES": "Summaries",
        "DISCORD_WEBHOOK_DAILY_REPORT": "Daily Reports"
    }
    
    for env_var, name in webhooks.items():
        webhook_url = os.getenv(env_var)
        print(f"\n🔍 Testing {name} webhook:")
        
        if not webhook_url:
            print(f"❌ {env_var} not set")
            continue
            
        # Validate URL format
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            print(f"❌ Invalid webhook URL format")
            continue
            
        print(f"📋 URL: {webhook_url[:50]}...")
        
        # Test webhook
        try:
            test_payload = {
                "content": f"🧪 Test from diagnostics - {name}",
                "embeds": [{
                    "title": f"{name} Webhook Test",
                    "description": "Testing webhook connectivity",
                    "color": 3447003,
                    "fields": [
                        {"name": "Status", "value": "Testing", "inline": True},
                        {"name": "Time", "value": datetime.now().strftime("%H:%M:%S"), "inline": True}
                    ]
                }]
            }
            
            response = requests.post(webhook_url, json=test_payload, timeout=10)
            
            if response.status_code in [200, 204]:
                print(f"✅ {name} webhook working!")
            else:
                print(f"❌ {name} webhook failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ {name} webhook error: {str(e)}")

def test_channel_tracking():
    """Test channel tracking functionality"""
    print("\n📺 CHANNEL TRACKING TEST")
    print("=" * 50)
    
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        print("❌ BACKEND_URL not configured - channel tracking requires backend")
        return
        
    print(f"Backend URL: {backend_url}")
    
    # Test backend endpoints
    endpoints_to_test = [
        "/api/health",
        "/api/channels/status", 
        "/api/scheduler/status"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(f"{backend_url}{endpoint}", timeout=10)
            print(f"📡 {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if endpoint == "/api/channels/status":
                    total_channels = data.get("total_channels", 0)
                    print(f"   📊 Tracking {total_channels} channels")
                    
                    if "channels" in data:
                        for channel_info in data["channels"][:3]:  # Show first 3
                            channel = channel_info.get("channel", "Unknown")
                            status = channel_info.get("status", "Unknown")
                            print(f"   📺 {channel}: {status}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
                
        except Exception as e:
            print(f"📡 {endpoint}: ❌ {str(e)}")

def test_supabase_connection():
    """Test Supabase database connection"""
    print("\n🗄️ SUPABASE CONNECTION TEST")
    print("=" * 50)
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not configured")
        print(f"   URL set: {'✅' if supabase_url else '❌'}")
        print(f"   Key set: {'✅' if supabase_key else '❌'}")
        return
        
    try:
        from shared.supabase_utils import get_config
        
        print("🔍 Testing Supabase connection...")
        config = get_config()
        
        if config:
            print("✅ Supabase connection working")
            print(f"📋 Config keys: {list(config.keys())}")
        else:
            print("❌ Supabase connection failed - no config returned")
            
    except Exception as e:
        print(f"❌ Supabase error: {str(e)}")

async def main():
    """Run comprehensive diagnostics for reported issues"""
    print("🔧 COMPREHENSIVE ISSUE DIAGNOSTICS")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test each reported issue
    await test_transcription_detailed()
    test_youtube_api_directly()
    test_discord_webhooks_detailed()
    test_channel_tracking()
    test_supabase_connection()
    
    print("\n" + "=" * 60)
    print("🎯 ISSUE SUMMARY")
    print("=" * 60)
    
    print("1. 🎬 TRANSCRIPTION:")
    print("   - Check if youtube_transcript_api is working")
    print("   - Verify Supabase connection for caching")
    print("   - Test with different video types")
    
    print("\n2. 📺 CHANNEL TRACKING:")
    print("   - Requires BACKEND_URL to be set")
    print("   - Backend service must be deployed separately")
    print("   - Check backend health endpoints")
    
    print("\n3. 📨 DISCORD WEBHOOKS:")
    print("   - Verify webhook URLs are still valid")
    print("   - Check Discord server permissions")
    print("   - Test webhook endpoints manually")
    
    print("\n💡 NEXT STEPS:")
    print("1. Fix any failing tests above")
    print("2. Check Railway environment variables")
    print("3. Verify Discord webhook URLs haven't expired")
    print("4. Ensure backend service is deployed if needed")

if __name__ == "__main__":
    asyncio.run(main())
