#!/usr/bin/env python3
"""
Quick Railway Deployment Monitor
Check if your Railway deployment is working
"""

import requests
import time
from datetime import datetime

def check_deployment(url):
    """Quick check if Railway deployment is live"""
    print(f"🧪 Testing Railway deployment at: {url}")
    print(f"📅 Test time: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 50)
    
    try:
        print("🔄 Attempting connection...")
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            print("✅ SUCCESS: Railway deployment is accessible!")
            
            # Check if it's Streamlit
            content = response.text.lower()
            if 'streamlit' in content or 'youtube summary bot' in content:
                print("✅ Streamlit app detected")
                print("✅ YouTube Summary Bot title found")
            else:
                print("⚠️  Response doesn't appear to be the expected app")
            
            # Check for errors
            if 'error' in content or 'exception' in content:
                print("⚠️  Potential errors detected in response")
            else:
                print("✅ No obvious errors in response")
            
            print(f"📊 Response size: {len(response.text)} characters")
            print("🎉 Deployment appears to be working!")
            return True
            
        else:
            print(f"❌ ERROR: Got status code {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Request took too long (app might be cold starting)")
        print("💡 Try again in 30-60 seconds for cold starts")
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Can't reach the URL")
        print("💡 Check if Railway deployment is complete")
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {str(e)}")
        return False

def main():
    print("🚀 Railway Deployment Monitor")
    print("=" * 40)
    print("Enter your Railway deployment URL to test it")
    print("Example: https://your-app-name.railway.app")
    print()
    
    url = input("Railway URL: ").strip()
    
    if not url:
        print("❌ No URL provided")
        return
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    print()
    success = check_deployment(url)
    
    print()
    if success:
        print("🎯 NEXT STEPS:")
        print("1. Test the 3-tab interface (Video Processor, Channel Manager, System Test)")
        print("2. Try processing a video: https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        print("3. Check System Test tab for environment variable status")
        print("4. Set OPENAI_API_KEY in Railway for full functionality")
    else:
        print("🔧 TROUBLESHOOTING:")
        print("1. Check Railway dashboard for deployment status")
        print("2. Verify build logs for errors")
        print("3. Ensure environment variables are set")
        print("4. Wait for cold start if recently deployed")

if __name__ == "__main__":
    main()
