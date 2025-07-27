#!/usr/bin/env python3
"""
Railway Deployment Quick Diagnosis
Tests critical functionality and provides Railway-specific troubleshooting
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def check_critical_imports():
    """Check if critical modules can be imported"""
    print("🔍 Testing Critical Imports")
    print("-" * 40)
    
    imports_to_test = [
        ("streamlit", "Streamlit framework"),
        ("requests", "HTTP requests"),
        ("youtube_transcript_api", "YouTube transcript API"),
        ("openai", "OpenAI API"),
        ("fastapi", "FastAPI framework"),
        ("supabase", "Supabase client"),
        ("aiohttp", "Async HTTP client"),
        ("uvicorn", "ASGI server")
    ]
    
    failed_imports = []
    
    for module, description in imports_to_test:
        try:
            __import__(module)
            print(f"✅ {module} - {description}")
        except ImportError as e:
            print(f"❌ {module} - {description}: {e}")
            failed_imports.append(module)
    
    return failed_imports

def test_shared_modules():
    """Test shared module imports and basic functionality"""
    print("\n🔧 Testing Shared Modules")
    print("-" * 40)
    
    try:
        from shared.transcript import extract_video_id
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(test_url)
        if video_id == "dQw4w9WgXcQ":
            print("✅ shared.transcript.extract_video_id - Working correctly")
        else:
            print(f"❌ shared.transcript.extract_video_id - Wrong result: {video_id}")
    except Exception as e:
        print(f"❌ shared.transcript.extract_video_id - Import/execution failed: {e}")
    
    try:
        from shared.summarize import DEFAULT_SUMMARY_PROMPT
        if DEFAULT_SUMMARY_PROMPT and len(DEFAULT_SUMMARY_PROMPT) > 10:
            print("✅ shared.summarize.DEFAULT_SUMMARY_PROMPT - Available")
        else:
            print("❌ shared.summarize.DEFAULT_SUMMARY_PROMPT - Empty or invalid")
    except Exception as e:
        print(f"❌ shared.summarize - Import failed: {e}")
    
    try:
        from shared.discord_utils import send_discord_message
        print("✅ shared.discord_utils - Imported successfully")
    except Exception as e:
        print(f"❌ shared.discord_utils - Import failed: {e}")

def test_backend_startup():
    """Test if backend can start up"""
    print("\n🚀 Testing Backend Startup")
    print("-" * 40)
    
    try:
        import backend.main
        app = backend.main.app
        if app:
            print("✅ Backend FastAPI app created successfully")
            
            # Check if health endpoint exists
            routes = [route.path for route in app.routes]
            if "/api/health" in routes:
                print("✅ Health endpoint configured")
            else:
                print("❌ Health endpoint missing")
            
            print(f"✅ Total API routes: {len([r for r in routes if r.startswith('/api')])}")
        else:
            print("❌ Backend app creation failed")
    except Exception as e:
        print(f"❌ Backend startup failed: {e}")

def test_frontend_streamlit():
    """Test Streamlit app basic structure"""
    print("\n🎨 Testing Frontend Structure")
    print("-" * 40)
    
    try:
        import streamlit as st
        print("✅ Streamlit imported successfully")
        
        # Check if app.py is accessible
        frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
        if os.path.exists(frontend_path):
            print("✅ Frontend app.py exists")
            
            # Read and check basic structure
            with open(frontend_path, 'r') as f:
                content = f.read()
            
            if "def main():" in content:
                print("✅ Main function defined")
            else:
                print("❌ Main function missing")
            
            if "st.set_page_config" in content:
                print("✅ Page config set")
            else:
                print("❌ Page config missing")
            
            if "st.tabs(" in content:
                print("✅ Tab interface configured")
            else:
                print("❌ Tab interface missing")
                
        else:
            print("❌ Frontend app.py not found")
    except Exception as e:
        print(f"❌ Frontend test failed: {e}")

def check_railway_specific():
    """Check Railway-specific configuration"""
    print("\n🚂 Railway Configuration Check")
    print("-" * 40)
    
    # Check start script
    start_script = os.path.join(os.path.dirname(__file__), "start.sh")
    if os.path.exists(start_script):
        print("✅ start.sh exists")
        with open(start_script, 'r') as f:
            content = f.read()
        if "streamlit run" in content:
            print("✅ Streamlit start command found")
        else:
            print("❌ Streamlit start command missing")
    else:
        print("❌ start.sh missing")
    
    # Check Procfile
    procfile = os.path.join(os.path.dirname(__file__), "Procfile")
    if os.path.exists(procfile):
        print("✅ Procfile exists")
    else:
        print("❌ Procfile missing")
    
    # Check railway.json
    railway_json = os.path.join(os.path.dirname(__file__), "railway.json")
    if os.path.exists(railway_json):
        print("✅ railway.json exists")
    else:
        print("❌ railway.json missing")
    
    # Check runtime.txt
    runtime_txt = os.path.join(os.path.dirname(__file__), "runtime.txt")
    if os.path.exists(runtime_txt):
        print("✅ runtime.txt exists")
        with open(runtime_txt, 'r') as f:
            python_version = f.read().strip()
        print(f"✅ Python version: {python_version}")
    else:
        print("❌ runtime.txt missing")

def generate_railway_troubleshooting():
    """Generate Railway-specific troubleshooting guide"""
    print("\n🔧 Railway Troubleshooting Guide")
    print("-" * 40)
    
    print("Common Railway deployment issues and solutions:")
    print()
    print("1. 📦 DEPENDENCIES")
    print("   - Ensure all dependencies are in requirements.txt")
    print("   - Use compatible versions (e.g., streamlit>=1.28.0)")
    print("   - Check for missing system dependencies")
    print()
    print("2. 🔧 ENVIRONMENT VARIABLES")
    print("   - Set OPENAI_API_KEY in Railway environment")
    print("   - Configure Discord webhooks if needed")
    print("   - Set BACKEND_URL if using separate backend")
    print()
    print("3. 🚀 START COMMAND")
    print("   - Railway should use: ./start.sh")
    print("   - start.sh should run: streamlit run frontend/app.py")
    print("   - Ensure correct port binding: --server.port=$PORT")
    print()
    print("4. 📁 FILE STRUCTURE")
    print("   - Frontend in frontend/ directory")
    print("   - Shared modules in shared/ directory") 
    print("   - Proper Python path setup")
    print()
    print("5. 🔒 PERMISSIONS")
    print("   - Make start.sh executable: chmod +x start.sh")
    print("   - Check file permissions in deployment")
    print()
    print("6. 🐛 DEBUGGING")
    print("   - Check Railway deployment logs")
    print("   - Use Railway CLI: railway logs")
    print("   - Test locally first: ./start.sh")

def main():
    """Run comprehensive diagnosis"""
    print("🧪 Railway Deployment Diagnosis")
    print("=" * 50)
    print(f"📅 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python Version: {sys.version}")
    print(f"📂 Working Directory: {os.getcwd()}")
    print()
    
    # Run all tests
    failed_imports = check_critical_imports()
    test_shared_modules()
    test_backend_startup()
    test_frontend_streamlit()
    check_railway_specific()
    generate_railway_troubleshooting()
    
    # Final summary
    print("\n📊 DIAGNOSIS SUMMARY")
    print("-" * 40)
    
    if failed_imports:
        print(f"❌ Failed imports: {', '.join(failed_imports)}")
        print("   → Install missing dependencies")
    else:
        print("✅ All critical imports working")
    
    print("\n🎯 NEXT STEPS FOR RAILWAY:")
    print("1. Fix any failed imports by updating requirements.txt")
    print("2. Set required environment variables in Railway dashboard")
    print("3. Deploy and check Railway logs for runtime errors")
    print("4. Test deployment URL once live")
    
    # Save diagnosis report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report = {
        "timestamp": timestamp,
        "python_version": sys.version,
        "failed_imports": failed_imports,
        "working_directory": os.getcwd()
    }
    
    with open(f"railway_diagnosis_{timestamp}.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📋 Report saved: railway_diagnosis_{timestamp}.json")

if __name__ == "__main__":
    main()
