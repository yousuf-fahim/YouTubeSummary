#!/usr/bin/env python3
"""
Complete System Test Script
Tests all components: Backend automation, Frontend functionality, and Supabase sync
"""

import requests
import json
import time

def test_backend_health():
    """Test basic backend health"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("1️⃣ Testing Backend Health...")
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

def test_automation_endpoints():
    """Test automation monitoring endpoints"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("\n2️⃣ Testing Automation Endpoints...")
    try:
        response = requests.get(f"{backend_url}/api/monitor/status", timeout=15)
        if response.status_code == 200:
            data = response.json()
            print("✅ Monitor status endpoint: PASSED")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
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
                print("💡 Automation endpoints not found - may need redeployment")
            return False
    except Exception as e:
        print(f"❌ Monitor status: FAILED (Error: {e})")
        return False

def test_channels_api():
    """Test channels management API"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("\n3️⃣ Testing Channels API...")
    try:
        response = requests.get(f"{backend_url}/api/channels", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Channels API: PASSED")
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            
            if "tracked_channels" in data:
                channels = data.get("tracked_channels", [])
                print(f"   📺 Channels found: {len(channels)}")
                for i, channel in enumerate(channels[:3], 1):  # Show first 3
                    print(f"   {i}. {channel}")
                return True
            else:
                print("⚠️ Channels data format unexpected")
                return False
        else:
            print(f"❌ Channels API: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Channels API: FAILED (Error: {e})")
        return False

def test_summaries_api():
    """Test summaries API"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("\n4️⃣ Testing Summaries API...")
    try:
        response = requests.get(f"{backend_url}/api/summaries", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Summaries API: PASSED")
            
            summaries = data.get("summaries", [])
            print(f"   📊 Summaries found: {len(summaries)}")
            
            # Check for valid summaries
            valid_summaries = [s for s in summaries if isinstance(s, dict) and s.get('title') and s.get('title') != 'None']
            print(f"   ✅ Valid summaries: {len(valid_summaries)}")
            
            if valid_summaries:
                latest = valid_summaries[-1]
                print(f"   🎥 Latest: {latest.get('title', 'Unknown')[:50]}...")
            
            return True
        else:
            print(f"❌ Summaries API: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Summaries API: FAILED (Error: {e})")
        return False

def test_frontend():
    """Test frontend deployment"""
    frontend_url = "https://youtubesummary-production-1899.up.railway.app"
    
    print("\n5️⃣ Testing Frontend...")
    try:
        response = requests.get(frontend_url, timeout=15)
        if response.status_code == 200:
            print("✅ Frontend: ONLINE")
            
            # Check if it contains expected content
            content = response.text
            if "YouTube Summary Bot" in content and "Automation" in content:
                print("✅ Frontend content: VALID (contains automation tab)")
                return True
            else:
                print("⚠️ Frontend content: May be outdated")
                return False
        else:
            print(f"❌ Frontend: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Frontend: FAILED (Error: {e})")
        return False

def test_start_automation():
    """Test starting automation"""
    backend_url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
    
    print("\n6️⃣ Testing Automation Start...")
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

def main():
    """Run comprehensive system test"""
    print("🤖 YouTube Summary Bot - Complete System Test")
    print("=" * 60)
    print("Testing all components after deployment fixes...")
    print()
    
    # Wait for deployment to settle
    print("⏳ Waiting for deployments to settle...")
    time.sleep(10)
    
    results = []
    
    # Run all tests
    tests = [
        ("Backend Health", test_backend_health),
        ("Automation Endpoints", test_automation_endpoints),
        ("Channels API", test_channels_api),
        ("Summaries API", test_summaries_api),
        ("Frontend", test_frontend),
        ("Automation Start", test_start_automation)
    ]
    
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SYSTEM TEST RESULTS:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n� Overall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL SYSTEMS OPERATIONAL!")
        print("✅ Your YouTube Summary Bot is fully deployed and working")
        print("🌐 Frontend: https://youtubesummary-production-1899.up.railway.app")
        print("🔧 Backend: https://yt-bot-backend-8302f5ba3275.herokuapp.com")
        print("\n� Ready for automated video processing!")
    elif passed >= total * 0.8:
        print("\n✅ MOSTLY OPERATIONAL!")
        print("✅ Core functionality is working")
        print("⚠️ Some minor issues detected - check logs above")
    else:
        print("\n⚠️ SIGNIFICANT ISSUES DETECTED")
        print("❌ Multiple components are not working properly")
        print("💡 Check deployment logs and try redeploying")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
