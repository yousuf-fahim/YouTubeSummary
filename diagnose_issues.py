#!/usr/bin/env python3
"""
Comprehensive diagnostic script for YouTube Summary Bot
Helps identify what's not working and provides troubleshooting guidance
"""
import os
import sys
import requests
import json
from datetime import datetime

def test_environment():
    """Test environment variables and configuration"""
    print("🔍 ENVIRONMENT DIAGNOSTICS")
    print("=" * 50)
    
    # Critical environment variables
    env_vars = [
        "OPENAI_API_KEY",
        "BACKEND_URL", 
        "DISCORD_WEBHOOK_UPLOADS",
        "DISCORD_WEBHOOK_TRANSCRIPTS",
        "DISCORD_WEBHOOK_SUMMARIES", 
        "DISCORD_WEBHOOK_DAILY_REPORT",
        "SUPABASE_URL",
        "SUPABASE_KEY"
    ]
    
    env_status = {}
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Show only first 10 chars for security
            masked_value = value[:10] + "..." if len(value) > 10 else value
            env_status[var] = f"✅ SET ({masked_value})"
        else:
            env_status[var] = "❌ MISSING"
    
    for var, status in env_status.items():
        print(f"{var}: {status}")
    
    return env_status

def test_backend_connectivity():
    """Test backend API connectivity"""
    print("\n🔗 BACKEND CONNECTIVITY")
    print("=" * 50)
    
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        print("❌ BACKEND_URL not configured")
        return False
    
    print(f"Backend URL: {backend_url}")
    
    # Test endpoints
    endpoints = [
        "/api/health",
        "/api/stats", 
        "/api/channels/status",
        "/api/scheduler/status"
    ]
    
    results = {}
    for endpoint in endpoints:
        try:
            response = requests.get(f"{backend_url}{endpoint}", timeout=10)
            if response.status_code == 200:
                results[endpoint] = f"✅ OK ({response.status_code})"
            else:
                results[endpoint] = f"⚠️ ERROR {response.status_code}"
        except requests.exceptions.Timeout:
            results[endpoint] = "❌ TIMEOUT"
        except requests.exceptions.ConnectionError:
            results[endpoint] = "❌ CONNECTION ERROR"
        except Exception as e:
            results[endpoint] = f"❌ ERROR: {str(e)}"
    
    for endpoint, result in results.items():
        print(f"{endpoint}: {result}")
    
    return all("✅" in result for result in results.values())

def test_openai_api():
    """Test OpenAI API connectivity"""
    print("\n🤖 OPENAI API TEST")
    print("=" * 50)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not configured")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ OpenAI API connection successful")
            return True
        else:
            print(f"❌ OpenAI API error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ OpenAI API test failed: {str(e)}")
        return False

def test_discord_webhooks():
    """Test Discord webhook connectivity"""
    print("\n📨 DISCORD WEBHOOKS TEST")
    print("=" * 50)
    
    webhooks = {
        "uploads": os.getenv("DISCORD_WEBHOOK_UPLOADS"),
        "transcripts": os.getenv("DISCORD_WEBHOOK_TRANSCRIPTS"), 
        "summaries": os.getenv("DISCORD_WEBHOOK_SUMMARIES"),
        "reports": os.getenv("DISCORD_WEBHOOK_DAILY_REPORT")
    }
    
    results = {}
    for name, webhook_url in webhooks.items():
        if not webhook_url:
            results[name] = "❌ NOT CONFIGURED"
            continue
            
        try:
            # Simple test payload
            test_payload = {
                "content": f"🧪 Test message from diagnostic script - {name.title()} webhook",
                "embeds": [{
                    "title": "Diagnostic Test",
                    "description": f"Testing {name} webhook connectivity",
                    "color": 3447003,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            response = requests.post(webhook_url, json=test_payload, timeout=10)
            if response.status_code in [200, 204]:
                results[name] = "✅ WORKING"
            else:
                results[name] = f"❌ ERROR {response.status_code}"
                
        except Exception as e:
            results[name] = f"❌ FAILED: {str(e)}"
    
    for name, result in results.items():
        print(f"{name.capitalize()}: {result}")
    
    return results

def test_shared_modules():
    """Test shared module imports"""
    print("\n📦 SHARED MODULES TEST")
    print("=" * 50)
    
    # Add project root to path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(project_root)
    
    modules_to_test = [
        "shared.transcript",
        "shared.summarize", 
        "shared.discord_utils",
        "shared.supabase_utils",
        "shared.youtube_tracker"
    ]
    
    results = {}
    for module in modules_to_test:
        try:
            __import__(module)
            results[module] = "✅ IMPORTED"
        except ImportError as e:
            results[module] = f"❌ IMPORT ERROR: {str(e)}"
        except Exception as e:
            results[module] = f"❌ ERROR: {str(e)}"
    
    for module, result in results.items():
        print(f"{module}: {result}")
    
    return results

def generate_troubleshooting_report():
    """Generate comprehensive troubleshooting report"""
    print("\n" + "=" * 70)
    print("📋 TROUBLESHOOTING REPORT")
    print("=" * 70)
    
    # Run all tests
    env_status = test_environment()
    backend_ok = test_backend_connectivity()
    openai_ok = test_openai_api()
    webhook_results = test_discord_webhooks()
    module_results = test_shared_modules()
    
    # Analyze issues
    issues = []
    suggestions = []
    
    # Check for missing critical env vars
    critical_missing = [var for var, status in env_status.items() 
                       if "❌" in status and var in ["OPENAI_API_KEY", "BACKEND_URL"]]
    
    if critical_missing:
        issues.append(f"❌ Critical environment variables missing: {', '.join(critical_missing)}")
        suggestions.append("🔧 Set missing environment variables in Railway dashboard")
    
    if not backend_ok:
        issues.append("❌ Backend API not responding")
        suggestions.append("🔧 Check if backend service is deployed and running")
        suggestions.append("🔧 Verify BACKEND_URL points to correct Railway service")
    
    if not openai_ok:
        issues.append("❌ OpenAI API not accessible")
        suggestions.append("🔧 Verify OPENAI_API_KEY is valid and has credits")
    
    webhook_issues = [name for name, result in webhook_results.items() if "❌" in result]
    if webhook_issues:
        issues.append(f"❌ Discord webhooks failing: {', '.join(webhook_issues)}")
        suggestions.append("🔧 Check Discord webhook URLs are still valid")
    
    module_issues = [mod for mod, result in module_results.items() if "❌" in result]
    if module_issues:
        issues.append(f"❌ Shared modules not loading: {len(module_issues)} modules")
        suggestions.append("🔧 Check if all dependencies are installed")
    
    # Print summary
    print("\n🚨 IDENTIFIED ISSUES:")
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ No critical issues detected")
    
    print("\n💡 SUGGESTED FIXES:")
    if suggestions:
        for suggestion in suggestions:
            print(f"  {suggestion}")
    else:
        print("  🎉 System appears to be configured correctly")
    
    # Generate status summary
    total_tests = 5
    passed_tests = sum([
        1 if not critical_missing else 0,
        1 if backend_ok else 0, 
        1 if openai_ok else 0,
        1 if not webhook_issues else 0,
        1 if not module_issues else 0
    ])
    
    print(f"\n📊 OVERALL HEALTH: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All systems operational!")
    elif passed_tests >= 3:
        print("⚠️ Some issues detected but core functionality should work")
    else:
        print("❌ Multiple critical issues - system may not function properly")

if __name__ == "__main__":
    print("🤖 YouTube Summary Bot - System Diagnostics")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    generate_troubleshooting_report()
    
    print("\n" + "=" * 70)
    print("Run this script periodically to monitor system health")
    print("For Railway deployment issues, check the Railway dashboard logs")
    print("=" * 70)
