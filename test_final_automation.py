#!/usr/bin/env python3
"""
Backend Automation Test Script
Verifies that the automation endpoints are working on the deployed backend
"""

import requests
import json

def test_backend_automation():
    """Test the deployed backend automation features"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("🔍 Testing Backend Automation Features...")
    print(f"🌐 Backend URL: {backend_url}")
    print("=" * 60)
    
    # Test 1: Health check
    print("1️⃣ Testing Health Check...")
    try:
        response = requests.get(f"{backend_url}/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check: PASSED")
        else:
            print(f"❌ Health check: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Health check: FAILED (Error: {e})")
        return False
    
    # Test 2: Monitor status (automation endpoint)
    print("\n2️⃣ Testing Automation Status...")
    try:
        response = requests.get(f"{backend_url}/api/monitor/status", timeout=15)
        if response.status_code == 200:
            data = response.json()
            print("✅ Monitor status: PASSED")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            # Check if automation features are present
            if data.get("success") and "monitoring" in data:
                print("✅ Automation features: DETECTED")
                monitoring = data.get("monitoring", {})
                print(f"   📺 Channels tracked: {monitoring.get('channels_tracked', 0)}")
                print(f"   🤖 Scheduler running: {monitoring.get('scheduler_running', False)}")
                return True
            else:
                print("⚠️ Automation features: NOT FULLY CONFIGURED")
                return False
        else:
            print(f"❌ Monitor status: FAILED (Status: {response.status_code})")
            if response.status_code == 404:
                print("💡 This suggests the automation endpoints are not deployed")
            return False
    except Exception as e:
        print(f"❌ Monitor status: FAILED (Error: {e})")
        return False

def test_start_automation():
    """Test starting the automation"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("\n3️⃣ Testing Automation Start...")
    try:
        response = requests.post(f"{backend_url}/api/monitor/start", timeout=15)
        if response.status_code == 200:
            data = response.json()
            print("✅ Automation start: PASSED")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ Automation start: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Automation start: FAILED (Error: {e})")
        return False

if __name__ == "__main__":
    print("🤖 YouTube Summary Bot - Backend Automation Test")
    print("Testing deployed automation features on Heroku...")
    print()
    
    # Run tests
    status_ok = test_backend_automation()
    
    if status_ok:
        print("\n🎉 BACKEND AUTOMATION IS DEPLOYED AND WORKING!")
        print("✅ Your automation features are available")
        
        # Try to start automation
        start_ok = test_start_automation()
        if start_ok:
            print("✅ Automation can be started remotely")
        else:
            print("⚠️ Automation start might need manual trigger")
    else:
        print("\n❌ BACKEND AUTOMATION NOT FULLY DEPLOYED")
        print("💡 The latest automation code may not be deployed yet")
    
    print("\n" + "=" * 60)
    print("🌐 Backend URL: https://yt-bot-backend-8302f5ba3275.herokuapp.com")
    print("🔧 Frontend URL: https://youtubesummary-production-1899.up.railway.app")
