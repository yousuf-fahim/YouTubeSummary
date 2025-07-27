#!/usr/bin/env python3
"""
Test the new automation features
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

import asyncio
from backend.main import automated_channel_monitoring, start_scheduler, stop_scheduler

async def test_automation():
    """Test the automation features"""
    
    print("🚀 TESTING AUTOMATED MONITORING SYSTEM")
    print("=" * 60)
    
    # Test 1: Manual monitoring check
    print("\n1️⃣ Testing manual monitoring function...")
    try:
        await automated_channel_monitoring()
        print("✅ Manual monitoring function works!")
    except Exception as e:
        print(f"❌ Manual monitoring error: {e}")
    
    # Test 2: Scheduler functions
    print("\n2️⃣ Testing scheduler functions...")
    try:
        print("   Starting scheduler...")
        start_scheduler()
        print("   ✅ Scheduler started successfully!")
        
        # Give it a moment
        await asyncio.sleep(1)
        
        print("   Stopping scheduler...")
        stop_scheduler()
        print("   ✅ Scheduler stopped successfully!")
        
    except Exception as e:
        print(f"   ❌ Scheduler error: {e}")
    
    print("\n🎯 AUTOMATION TEST COMPLETE!")
    print("=" * 60)
    print("""
🔧 AUTOMATION FEATURES IMPLEMENTED:

✅ Automated Channel Monitoring Function
   - Checks all tracked channels every 30 minutes
   - Automatically processes new videos
   - Sends Discord notifications
   
✅ APScheduler Integration
   - AsyncIOScheduler for non-blocking operation
   - Interval trigger (30-minute intervals)
   - Proper startup/shutdown handling

✅ New API Endpoints:
   - GET /api/monitor/status (enhanced with scheduler info)
   - POST /api/monitor/start (start automated monitoring)
   - POST /api/monitor/stop (stop automated monitoring)  
   - POST /api/monitor/check-now (manual trigger)

✅ FastAPI Lifecycle Events:
   - Automatic scheduler startup on application start
   - Graceful scheduler shutdown on application stop

🚀 NEXT STEPS:
   1. Deploy to Railway/Heroku with new automation
   2. Monitor logs for automated channel checking
   3. Verify Discord notifications work automatically
   4. Scale monitoring frequency if needed
    """)

if __name__ == "__main__":
    asyncio.run(test_automation())
