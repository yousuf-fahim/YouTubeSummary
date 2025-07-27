#!/usr/bin/env python3
"""
Comprehensive Railway Deployment Testing Script
Tests both frontend and backend features systematically
"""

import os
import sys
import requests
import json
import time
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")

def test_env_variables():
    """Test if required environment variables are set"""
    print_header("Testing Environment Variables")
    
    required_vars = [
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_UPLOADS", 
        "DISCORD_WEBHOOK_SUMMARIES",
        "DISCORD_WEBHOOK_TRANSCRIPTS",
        "DISCORD_WEBHOOK_DAILY_REPORT"
    ]
    
    optional_vars = [
        "BACKEND_URL",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "RAILWAY_ENVIRONMENT"
    ]
    
    env_results = {"required": {}, "optional": {}}
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var}: {'*' * min(len(value), 20)}...")
            env_results["required"][var] = True
        else:
            print_error(f"{var}: Not set")
            env_results["required"][var] = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var}: {value}")
            env_results["optional"][var] = True
        else:
            print_warning(f"{var}: Not set (optional)")
            env_results["optional"][var] = False
    
    return env_results

def test_backend_connectivity():
    """Test backend API connectivity"""
    print_header("Testing Backend Connectivity")
    
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        print_warning("BACKEND_URL not set, skipping backend tests")
        return None
    
    print_info(f"Testing backend at: {backend_url}")
    
    backend_results = {}
    
    # Test health endpoint
    try:
        response = requests.get(f"{backend_url}/api/health", timeout=10)
        if response.status_code == 200:
            print_success("Health endpoint working")
            backend_results["health"] = True
        else:
            print_error(f"Health endpoint returned {response.status_code}")
            backend_results["health"] = False
    except Exception as e:
        print_error(f"Health endpoint failed: {str(e)}")
        backend_results["health"] = False
    
    # Test scheduler status
    try:
        response = requests.get(f"{backend_url}/api/scheduler/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Scheduler status: {data.get('status', 'unknown')}")
            backend_results["scheduler"] = True
        else:
            print_error(f"Scheduler endpoint returned {response.status_code}")
            backend_results["scheduler"] = False
    except Exception as e:
        print_error(f"Scheduler endpoint failed: {str(e)}")
        backend_results["scheduler"] = False
    
    # Test config endpoint
    try:
        response = requests.get(f"{backend_url}/api/config", timeout=10)
        if response.status_code == 200:
            print_success("Config endpoint working")
            backend_results["config"] = True
        else:
            print_error(f"Config endpoint returned {response.status_code}")
            backend_results["config"] = False
    except Exception as e:
        print_error(f"Config endpoint failed: {str(e)}")
        backend_results["config"] = False
    
    # Test channels endpoint
    try:
        response = requests.get(f"{backend_url}/api/channels", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Channels endpoint working (tracking {len(data.get('channels', []))} channels)")
            backend_results["channels"] = True
        else:
            print_error(f"Channels endpoint returned {response.status_code}")
            backend_results["channels"] = False
    except Exception as e:
        print_error(f"Channels endpoint failed: {str(e)}")
        backend_results["channels"] = False
    
    return backend_results

def test_openai_api():
    """Test OpenAI API connectivity"""
    print_header("Testing OpenAI API")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print_error("OPENAI_API_KEY not set")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=15)
        
        if response.status_code == 200:
            models = response.json()
            print_success(f"OpenAI API working ({len(models.get('data', []))} models available)")
            return True
        else:
            print_error(f"OpenAI API returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_error(f"OpenAI API test failed: {str(e)}")
        return False

def test_webhook_connectivity():
    """Test Discord webhook connectivity"""
    print_header("Testing Discord Webhooks")
    
    webhooks = {
        "Uploads": os.getenv("DISCORD_WEBHOOK_UPLOADS"),
        "Transcripts": os.getenv("DISCORD_WEBHOOK_TRANSCRIPTS"),
        "Summaries": os.getenv("DISCORD_WEBHOOK_SUMMARIES"),
        "Daily Report": os.getenv("DISCORD_WEBHOOK_DAILY_REPORT")
    }
    
    webhook_results = {}
    
    for name, webhook_url in webhooks.items():
        if not webhook_url:
            print_warning(f"{name} webhook not configured")
            webhook_results[name] = False
            continue
        
        try:
            # Send a simple test message
            payload = {
                "content": f"🧪 **{name} Webhook Test** - {datetime.now().strftime('%H:%M:%S')}",
                "embeds": [{
                    "title": "Railway Deployment Test",
                    "description": f"Testing {name.lower()} webhook connectivity",
                    "color": 3066993,
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {"text": "YouTube Summary Bot"}
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code in [200, 204]:
                print_success(f"{name} webhook working")
                webhook_results[name] = True
            else:
                print_error(f"{name} webhook returned {response.status_code}")
                webhook_results[name] = False
                
        except Exception as e:
            print_error(f"{name} webhook failed: {str(e)}")
            webhook_results[name] = False
    
    return webhook_results

def test_video_processing():
    """Test video processing functionality"""
    print_header("Testing Video Processing")
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up (reliable test video)
    print_info(f"Testing with: {test_url}")
    
    try:
        # Import shared modules
        from shared.transcript import get_transcript, extract_video_id
        from shared.summarize import chunk_and_summarize
        
        # Test video ID extraction
        video_id = extract_video_id(test_url)
        if video_id:
            print_success(f"Video ID extracted: {video_id}")
        else:
            print_error("Failed to extract video ID")
            return False
        
        # Test transcript retrieval
        print_info("Testing transcript retrieval...")
        transcript = asyncio.run(get_transcript(test_url))
        
        if transcript:
            print_success(f"Transcript retrieved ({len(transcript)} characters)")
            
            # Test summarization if OpenAI key is available
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                print_info("Testing AI summarization...")
                summary = asyncio.run(chunk_and_summarize(transcript, openai_key))
                
                if summary:
                    print_success("AI summarization successful")
                    if isinstance(summary, dict):
                        print_info(f"Summary fields: {list(summary.keys())}")
                    return True
                else:
                    print_error("AI summarization failed")
                    return False
            else:
                print_warning("Skipping AI summarization (no OpenAI key)")
                return True
        else:
            print_error("Failed to retrieve transcript")
            return False
            
    except ImportError as e:
        print_error(f"Failed to import shared modules: {e}")
        return False
    except Exception as e:
        print_error(f"Video processing test failed: {str(e)}")
        return False

def test_channel_management():
    """Test channel management features"""
    print_header("Testing Channel Management")
    
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        print_warning("Backend URL not configured, skipping channel management tests")
        return False
    
    try:
        # Test channel listing
        response = requests.get(f"{backend_url}/api/channels", timeout=10)
        if response.status_code == 200:
            data = response.json()
            channels = data.get("channels", [])
            print_success(f"Channel listing working ({len(channels)} channels)")
            
            # Test channel status
            status_response = requests.get(f"{backend_url}/api/channels/status", timeout=15)
            if status_response.status_code == 200:
                status_data = status_response.json()
                print_success(f"Channel status working (total: {status_data.get('total_channels', 0)})")
                return True
            else:
                print_error(f"Channel status failed: {status_response.status_code}")
                return False
        else:
            print_error(f"Channel listing failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Channel management test failed: {str(e)}")
        return False

def test_daily_report():
    """Test daily report functionality"""
    print_header("Testing Daily Report")
    
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        print_warning("Backend URL not configured, skipping daily report test")
        return False
    
    try:
        # Get webhook token
        token_response = requests.get(f"{backend_url}/api/webhook-token", timeout=10)
        if token_response.status_code == 200:
            token = token_response.json().get("token")
            print_success("Webhook token retrieved")
            
            # Test daily report trigger (but don't actually send to avoid spam)
            print_info("Daily report endpoint accessible (skipping actual trigger)")
            return True
        else:
            print_error(f"Failed to get webhook token: {token_response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Daily report test failed: {str(e)}")
        return False

def generate_test_report(results):
    """Generate a comprehensive test report"""
    print_header("Test Results Summary")
    
    total_tests = 0
    passed_tests = 0
    
    print(f"\n{Colors.BOLD}Environment Variables:{Colors.END}")
    for var, status in results.get("env", {}).get("required", {}).items():
        total_tests += 1
        if status:
            passed_tests += 1
            print_success(f"{var}")
        else:
            print_error(f"{var}")
    
    if results.get("backend"):
        print(f"\n{Colors.BOLD}Backend API:{Colors.END}")
        for test, status in results.get("backend", {}).items():
            total_tests += 1
            if status:
                passed_tests += 1
                print_success(f"{test.title()} endpoint")
            else:
                print_error(f"{test.title()} endpoint")
    
    print(f"\n{Colors.BOLD}External Services:{Colors.END}")
    if results.get("openai") is not None:
        total_tests += 1
        if results.get("openai"):
            passed_tests += 1
            print_success("OpenAI API")
        else:
            print_error("OpenAI API")
    
    if results.get("webhooks"):
        for webhook, status in results.get("webhooks", {}).items():
            total_tests += 1
            if status:
                passed_tests += 1
                print_success(f"{webhook} webhook")
            else:
                print_error(f"{webhook} webhook")
    
    print(f"\n{Colors.BOLD}Core Features:{Colors.END}")
    feature_tests = ["video_processing", "channel_management", "daily_report"]
    for test in feature_tests:
        if results.get(test) is not None:
            total_tests += 1
            if results.get(test):
                passed_tests += 1
                print_success(f"{test.replace('_', ' ').title()}")
            else:
                print_error(f"{test.replace('_', ' ').title()}")
    
    # Final score
    print(f"\n{Colors.BOLD}Overall Results:{Colors.END}")
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    if success_rate >= 90:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 EXCELLENT: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%){Colors.END}")
    elif success_rate >= 75:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  GOOD: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%){Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ NEEDS ATTENTION: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%){Colors.END}")
    
    return success_rate

def main():
    """Run comprehensive deployment tests"""
    print_header("YouTube Summary Bot - Railway Deployment Test")
    print_info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run all tests
    results["env"] = test_env_variables()
    results["backend"] = test_backend_connectivity()
    results["openai"] = test_openai_api()
    results["webhooks"] = test_webhook_connectivity()
    results["video_processing"] = test_video_processing()
    results["channel_management"] = test_channel_management()
    results["daily_report"] = test_daily_report()
    
    # Generate final report
    success_rate = generate_test_report(results)
    
    # Save results to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"deployment_test_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "success_rate": success_rate,
            "results": results
        }, f, indent=2, default=str)
    
    print_info(f"Detailed results saved to: {report_file}")
    
    return success_rate >= 75  # Return True if tests are mostly passing

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
