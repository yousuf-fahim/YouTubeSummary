#!/usr/bin/env python3
"""
Test script for enhanced YouTube channel tracker
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

def test_enhanced_tracker():
    """Test the enhanced tracker functionality"""
    print("🧪 Testing Enhanced YouTube Channel Tracker")
    print("=" * 60)
    
    try:
        from shared.enhanced_tracker import enhanced_tracker
        
        # Test 1: Get current channels
        print("\n1️⃣ Testing get_tracked_channels()")
        result = enhanced_tracker.get_tracked_channels()
        print(f"✅ Current channels: {result}")
        
        # Test 2: Add a test channel
        print("\n2️⃣ Testing add_channel() with YouTube URL")
        test_channel = "https://www.youtube.com/channel/UCAuUUnT6oDeKwE6v1NGQxug"  # TED channel
        add_result = enhanced_tracker.add_channel(test_channel)
        print(f"✅ Add result: {add_result}")
        
        # Also test with @handle if the URL fails
        if not add_result.get("success"):
            print("\n2️⃣b Testing add_channel() with @handle")
            test_channel2 = "@TED"
            add_result2 = enhanced_tracker.add_channel(test_channel2)
            print(f"✅ Add result for @TED: {add_result2}")
            add_result = add_result2 if add_result2.get("success") else add_result
        
        if add_result.get("success"):
            # Test 3: Get latest videos
            print("\n3️⃣ Testing latest videos retrieval")
            channel_id = add_result.get("channel_id")
            if channel_id:
                latest_videos = enhanced_tracker.get_latest_videos(channel_id, limit=2)
                print(f"✅ Latest videos: {len(latest_videos)} videos found")
                for video in latest_videos:
                    print(f"   📹 {video.get('title', 'Unknown')} ({video.get('published_ago', 'Unknown time')})")
            
            # Test 4: Refresh channel videos
            print("\n4️⃣ Testing refresh_channel_videos()")
            refresh_result = enhanced_tracker.refresh_channel_videos(channel_id)
            print(f"✅ Refresh result: {refresh_result}")
            
            # Test 5: Remove the test channel
            print("\n5️⃣ Testing remove_channel()")
            remove_result = enhanced_tracker.remove_channel(channel_id)
            print(f"✅ Remove result: {remove_result}")
        
        print("\n🎉 All enhanced tracker tests completed!")
        
    except Exception as e:
        print(f"❌ Error testing enhanced tracker: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_enhanced_tracker()
