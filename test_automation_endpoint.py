#!/usr/bin/env python3
"""
Quick test of the automation endpoint
"""

import requests
import json

def test_automation_endpoint():
    url = "https://yt-bot-backend-8302f5ba3275.herokuapp.com/api/monitor/status"
    
    try:
        print(f"Testing: {url}")
        response = requests.get(url, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Response: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"JSON Response: {json.dumps(data, indent=2)}")
                
                if data.get("success"):
                    print("✅ Success field found: True")
                else:
                    print("❌ Success field missing or False")
                    
            except ValueError as e:
                print(f"❌ Invalid JSON: {e}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_automation_endpoint()
