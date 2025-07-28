#!/usr/bin/env python3
"""
Deployment verification script for YouTube Summary Bot
Tests both backend and frontend after deployment
"""

import requests
import time
import sys

def test_backend():
    """Test backend deployment"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("🔍 Testing Backend Deployment...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{backend_url}/api/health", timeout=10)
        if response.status_code == 200:
            print("✅ Backend health check: PASSED")
            return True
        else:
            print(f"❌ Backend health check: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Backend health check: FAILED (Error: {e})")
        return False

def test_frontend():
    """Test frontend deployment"""
    frontend_url = "https://youtubesummary-production-1899.up.railway.app"
    
    print("🔍 Testing Frontend Deployment...")
    
    try:
        response = requests.get(frontend_url, timeout=10)
        if response.status_code == 200:
            print("✅ Frontend health check: PASSED")
            return True
        else:
            print(f"❌ Frontend health check: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Frontend health check: FAILED (Error: {e})")
        return False

def test_automation():
    """Test automation endpoints"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("🔍 Testing Automation Features...")
    
    try:
        response = requests.get(f"{backend_url}/api/monitor/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Automation monitoring: PASSED")
                monitoring = data.get("monitoring", {})
                print(f"   📺 Channels tracked: {monitoring.get('channels_tracked', 0)}")
                print(f"   🤖 Scheduler running: {monitoring.get('scheduler_running', False)}")
                return True
            else:
                print("❌ Automation monitoring: FAILED (No success in response)")
                return False
        else:
            print(f"❌ Automation monitoring: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Automation monitoring: FAILED (Error: {e})")
        return False

def main():
    """Run all deployment tests"""
    print("🚀 YouTube Summary Bot - Deployment Verification")
    print("=" * 50)
    
    # Wait a moment for deployments to settle
    print("⏳ Waiting for deployments to settle...")
    time.sleep(5)
    
    results = []
    
    # Test backend
    backend_ok = test_backend()
    results.append(("Backend", backend_ok))
    
    print()
    
    # Test frontend
    frontend_ok = test_frontend()
    results.append(("Frontend", frontend_ok))
    
    print()
    
    # Test automation
    automation_ok = test_automation()
    results.append(("Automation", automation_ok))
    
    print()
    print("=" * 50)
    print("📊 DEPLOYMENT RESULTS:")
    
    all_passed = True
    for service, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {service}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ALL DEPLOYMENTS SUCCESSFUL!")
        print("🌐 Your YouTube Summary Bot is fully operational:")
        print("   Backend: https://yt-bot-backend-8302f5ba3275.herokuapp.com")
        print("   Frontend: https://youtubesummary-production-1899.up.railway.app")
    else:
        print("⚠️  Some deployments failed. Check the logs above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
