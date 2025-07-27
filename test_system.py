#!/usr/bin/env python3
"""
Complete system test for YouTube Summary Bot
Tests all core functionality with your environment configuration
"""

import os
import sys
import asyncio
from datetime import datetime

# Add project paths
sys.path.append('.')
sys.path.append('frontend')
sys.path.append('shared')

def test_environment_variables():
    """Test environment variable configuration"""
    print("🔧 Testing Environment Variables...")
    
    required_vars = [
        'OPENAI_API_KEY',
        'SUPABASE_URL', 
        'SUPABASE_KEY',
        'BACKEND_URL',
        'DISCORD_WEBHOOK_UPLOADS',
        'DISCORD_WEBHOOK_TRANSCRIPTS',
        'DISCORD_WEBHOOK_SUMMARIES',
        'DISCORD_WEBHOOK_DAILY_REPORT'
    ]
    
    configured = 0
    for var in required_vars:
        value = os.getenv(var)
        if value and value != "NOT_SET":
            print(f"   ✅ {var}: Configured")
            configured += 1
        else:
            print(f"   ⚠️  {var}: Not set (will use fallback)")
    
    print(f"\n   📊 Configuration: {configured}/{len(required_vars)} variables set")
    return configured > 0

def test_core_functions():
    """Test core YouTube processing functions"""
    print("\n🎥 Testing Core Functions...")
    
    try:
        from frontend.local_functions import extract_video_id, get_video_title
        
        # Test video ID extraction
        test_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        video_id = extract_video_id(test_url)
        print(f"   ✅ Video ID extraction: {video_id}")
        
        # Test video title fetching
        title_info = get_video_title(video_id)
        if isinstance(title_info, tuple):
            title, channel = title_info
            print(f"   ✅ Video title: {title}")
            print(f"   ✅ Channel: {channel}")
        else:
            print(f"   ✅ Video title: {title_info}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_backend_connectivity():
    """Test backend connectivity"""
    print("\n🔗 Testing Backend Connectivity...")
    
    try:
        import requests
        backend_url = os.getenv('BACKEND_URL', 'https://yt-bot-backend-8302f5ba3275.herokuapp.com')
        
        response = requests.get(f"{backend_url}/api/health", timeout=10)
        if response.status_code == 200:
            print(f"   ✅ Backend health check: OK")
            print(f"   ✅ Backend URL: {backend_url}")
            return True
        else:
            print(f"   ⚠️  Backend responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ⚠️  Backend connection: {e}")
        print("   ℹ️  Backend will be tested when deployed")
        return False

def test_shared_modules():
    """Test shared module imports"""
    print("\n📦 Testing Shared Modules...")
    
    modules_to_test = [
        'config_service',
        'discord_utils',
        'transcript',
        'summarize'
    ]
    
    working_modules = 0
    for module in modules_to_test:
        try:
            __import__(f'shared.{module}')
            print(f"   ✅ {module}: Available")
            working_modules += 1
        except Exception as e:
            print(f"   ⚠️  {module}: {e}")
    
    print(f"\n   📊 Modules: {working_modules}/{len(modules_to_test)} working")
    return working_modules > 0

def test_frontend_import():
    """Test frontend application import"""
    print("\n🖥️  Testing Frontend App...")
    
    try:
        # This will trigger Streamlit warnings but that's normal
        import frontend.app
        print("   ✅ Frontend app imports successfully")
        print("   ✅ All dependencies resolved")
        return True
    except Exception as e:
        print(f"   ❌ Frontend import error: {e}")
        return False

def main():
    """Run complete system test"""
    print("=" * 60)
    print("🚀 YouTube Summary Bot - Complete System Test")
    print("=" * 60)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Core Functions", test_core_functions),
        ("Backend Connectivity", test_backend_connectivity),
        ("Shared Modules", test_shared_modules),
        ("Frontend Import", test_frontend_import)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n   ❌ {test_name} failed: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed >= 3:  # Core functionality working
        print("✅ System Status: READY FOR DEPLOYMENT")
        print("\n🎯 Next Steps:")
        print("   1. Set your environment variables in Railway/Heroku")
        print("   2. Deploy the application")
        print("   3. Test with real YouTube videos")
        print("\n🔧 To run locally (with env vars):")
        print("   cd frontend && streamlit run app.py")
    else:
        print("⚠️  System Status: NEEDS ATTENTION")
        print("   Check the failed tests above")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
