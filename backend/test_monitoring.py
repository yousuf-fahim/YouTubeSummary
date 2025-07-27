#!/usr/bin/env python3
"""
Test channel monitoring functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    print(f"✅ Loaded environment from: {env_path}")
except ImportError:
    print("⚠️ python-dotenv not available, using system environment")

from shared.youtube_tracker import get_latest_videos_from_channel, extract_channel_id
from shared.supabase_utils import get_tracked_channels

def test_channel_monitoring():
    """Test if we can get latest videos from tracked channels"""
    
    print("🔍 Testing Channel Monitoring Functionality")
    print("=" * 60)
    
    # Get current tracked channels
    try:
        channels_data = get_tracked_channels()
        tracked_channels = channels_data.get("tracked_channels", [])
        print(f"📊 Found {len(tracked_channels)} tracked channels")
        print()
    except Exception as e:
        print(f"❌ Error getting tracked channels: {e}")
        return
    
    # Test a few channels
    test_channels = tracked_channels[:3]  # Test first 3 channels
    
    results = []
    
    for channel in test_channels:
        print(f"🔎 Testing channel: {channel}")
        
        try:
            # Extract channel ID
            channel_id = extract_channel_id(channel)
            print(f"   Extracted ID: {channel_id}")
            
            # Get latest videos
            latest = get_latest_videos_from_channel(channel)
            
            if latest:
                results.append({
                    "channel": channel,
                    "status": "✅ Working",
                    "latest_video": latest.get('title', 'No title'),
                    "video_id": latest.get('id', 'No ID'),
                    "published": latest.get('published', 'No date')
                })
                print(f"   ✅ Latest video: {latest.get('title', 'No title')}")
                print(f"   📹 Video ID: {latest.get('id', 'No ID')}")
            else:
                results.append({
                    "channel": channel,
                    "status": "⚠️ No videos found",
                    "error": "Could not retrieve latest video"
                })
                print(f"   ⚠️ No videos found")
                
        except Exception as e:
            results.append({
                "channel": channel,
                "status": "❌ Error",
                "error": str(e)
            })
            print(f"   ❌ Error: {str(e)}")
        
        print("-" * 40)
    
    # Summary
    print()
    print("📋 MONITORING TEST SUMMARY")
    print("=" * 60)
    
    working_count = sum(1 for r in results if "✅" in r["status"])
    
    for result in results:
        print(f"Channel: {result['channel']}")
        print(f"Status: {result['status']}")
        if "latest_video" in result:
            print(f"Latest: {result['latest_video']}")
        if "error" in result:
            print(f"Error: {result['error']}")
        print()
    
    print(f"🎯 Success Rate: {working_count}/{len(results)} channels working")
    
    if working_count > 0:
        print("✅ Channel monitoring functionality is working!")
    else:
        print("❌ Channel monitoring needs attention")
    
    return results

if __name__ == "__main__":
    test_channel_monitoring()
