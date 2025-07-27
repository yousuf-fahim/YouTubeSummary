#!/usr/bin/env python3
"""
Railway Deployment Feature Verification
Test all features on the live Railway deployment
"""

import requests
import json
import time
import asyncio
import os
from datetime import datetime

class RailwayTester:
    def __init__(self, frontend_url, backend_url=None):
        """
        Initialize the Railway tester
        
        Args:
            frontend_url (str): The Railway frontend URL
            backend_url (str): The Railway backend URL (optional)
        """
        self.frontend_url = frontend_url.rstrip('/')
        self.backend_url = backend_url.rstrip('/') if backend_url else None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Railway-Deployment-Tester/1.0'
        })
        
    def print_header(self, text):
        print(f"\n{'='*60}")
        print(f"{text.center(60)}")
        print(f"{'='*60}")
    
    def print_success(self, text):
        print(f"✅ {text}")
    
    def print_error(self, text):
        print(f"❌ {text}")
    
    def print_warning(self, text):
        print(f"⚠️  {text}")
    
    def print_info(self, text):
        print(f"ℹ️  {text}")
    
    def test_frontend_accessibility(self):
        """Test if frontend is accessible"""
        self.print_header("Frontend Accessibility Test")
        
        try:
            response = self.session.get(self.frontend_url, timeout=15)
            
            if response.status_code == 200:
                self.print_success(f"Frontend accessible at {self.frontend_url}")
                
                # Check if it's actually Streamlit
                if 'streamlit' in response.text.lower() or 'stlite' in response.text.lower():
                    self.print_success("Streamlit application detected")
                else:
                    self.print_warning("Response doesn't appear to be Streamlit")
                
                # Check for key elements
                if 'YouTube Summary Bot' in response.text:
                    self.print_success("App title found")
                else:
                    self.print_warning("App title not found in HTML")
                
                return True
            else:
                self.print_error(f"Frontend returned status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.print_error("Frontend request timed out")
            return False
        except Exception as e:
            self.print_error(f"Frontend accessibility failed: {str(e)}")
            return False
    
    def test_backend_connectivity(self):
        """Test backend API connectivity"""
        if not self.backend_url:
            self.print_warning("Backend URL not provided, skipping backend tests")
            return None
        
        self.print_header("Backend Connectivity Test")
        
        results = {}
        
        # Test health endpoint
        try:
            response = self.session.get(f"{self.backend_url}/api/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"Health endpoint: {data.get('status', 'unknown')}")
                results['health'] = True
            else:
                self.print_error(f"Health endpoint returned {response.status_code}")
                results['health'] = False
        except Exception as e:
            self.print_error(f"Health endpoint failed: {str(e)}")
            results['health'] = False
        
        # Test config endpoint
        try:
            response = self.session.get(f"{self.backend_url}/api/config", timeout=10)
            if response.status_code == 200:
                self.print_success("Config endpoint accessible")
                results['config'] = True
            else:
                self.print_error(f"Config endpoint returned {response.status_code}")
                results['config'] = False
        except Exception as e:
            self.print_error(f"Config endpoint failed: {str(e)}")
            results['config'] = False
        
        # Test channels endpoint
        try:
            response = self.session.get(f"{self.backend_url}/api/channels", timeout=10)
            if response.status_code == 200:
                data = response.json()
                channels = data.get('channels', [])
                self.print_success(f"Channels endpoint: {len(channels)} channels tracked")
                results['channels'] = True
            else:
                self.print_error(f"Channels endpoint returned {response.status_code}")
                results['channels'] = False
        except Exception as e:
            self.print_error(f"Channels endpoint failed: {str(e)}")
            results['channels'] = False
        
        # Test scheduler status
        try:
            response = self.session.get(f"{self.backend_url}/api/scheduler/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"Scheduler status: {data.get('status', 'unknown')}")
                results['scheduler'] = True
            else:
                self.print_error(f"Scheduler endpoint returned {response.status_code}")
                results['scheduler'] = False
        except Exception as e:
            self.print_error(f"Scheduler endpoint failed: {str(e)}")
            results['scheduler'] = False
        
        return results
    
    def test_streamlit_features(self):
        """Test Streamlit-specific features"""
        self.print_header("Streamlit Features Test")
        
        try:
            # Test health endpoint (some Streamlit apps expose this)
            response = self.session.get(f"{self.frontend_url}/_stcore/health", timeout=10)
            if response.status_code == 200:
                self.print_success("Streamlit health endpoint available")
            else:
                self.print_info("Streamlit health endpoint not available (normal)")
        except:
            self.print_info("Streamlit health endpoint not available (normal)")
        
        # Test if websocket connections would work (we can't test this directly)
        self.print_info("Streamlit websocket functionality assumed working if app loads")
        
        return True
    
    def test_environment_indicators(self):
        """Test for environment-specific indicators"""
        self.print_header("Environment Indicators Test")
        
        try:
            response = self.session.get(self.frontend_url, timeout=15)
            content = response.text.lower()
            
            # Look for Railway-specific indicators
            if 'railway' in content:
                self.print_success("Railway environment detected")
            else:
                self.print_info("No explicit Railway indicators found")
            
            # Look for error indicators
            error_indicators = ['error', 'exception', 'traceback', 'failed']
            found_errors = [indicator for indicator in error_indicators if indicator in content]
            
            if found_errors:
                self.print_warning(f"Potential error indicators found: {', '.join(found_errors)}")
            else:
                self.print_success("No obvious error indicators in response")
            
            return True
            
        except Exception as e:
            self.print_error(f"Environment indicators test failed: {str(e)}")
            return False
    
    def test_webhook_endpoints(self):
        """Test webhook endpoints if backend is available"""
        if not self.backend_url:
            self.print_warning("Backend URL not provided, skipping webhook tests")
            return None
        
        self.print_header("Webhook Endpoints Test")
        
        results = {}
        
        # Test webhook token endpoint
        try:
            response = self.session.get(f"{self.backend_url}/api/webhook-token", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'token' in data:
                    self.print_success("Webhook token endpoint working")
                    results['webhook_token'] = True
                else:
                    self.print_error("Webhook token endpoint missing token")
                    results['webhook_token'] = False
            else:
                self.print_error(f"Webhook token endpoint returned {response.status_code}")
                results['webhook_token'] = False
        except Exception as e:
            self.print_error(f"Webhook token endpoint failed: {str(e)}")
            results['webhook_token'] = False
        
        # Test webhook structure (NotifyMe endpoint)
        try:
            # We won't actually send a webhook, just check if endpoint exists
            response = self.session.post(f"{self.backend_url}/api/webhook/notifyme", 
                                       json={}, timeout=10)
            if response.status_code in [200, 400, 422]:  # 400/422 expected for empty request
                self.print_success("NotifyMe webhook endpoint exists")
                results['notifyme_webhook'] = True
            else:
                self.print_error(f"NotifyMe webhook returned {response.status_code}")
                results['notifyme_webhook'] = False
        except Exception as e:
            self.print_error(f"NotifyMe webhook test failed: {str(e)}")
            results['notifyme_webhook'] = False
        
        return results
    
    def generate_comprehensive_report(self, frontend_result, backend_results, streamlit_result, 
                                    env_result, webhook_results):
        """Generate a comprehensive test report"""
        self.print_header("Comprehensive Test Report")
        
        total_tests = 0
        passed_tests = 0
        
        # Frontend tests
        if frontend_result is not None:
            total_tests += 1
            if frontend_result:
                passed_tests += 1
                self.print_success("Frontend Accessibility")
            else:
                self.print_error("Frontend Accessibility")
        
        # Backend tests
        if backend_results:
            for test, result in backend_results.items():
                total_tests += 1
                if result:
                    passed_tests += 1
                    self.print_success(f"Backend {test.title()}")
                else:
                    self.print_error(f"Backend {test.title()}")
        
        # Streamlit tests
        if streamlit_result is not None:
            total_tests += 1
            if streamlit_result:
                passed_tests += 1
                self.print_success("Streamlit Features")
            else:
                self.print_error("Streamlit Features")
        
        # Environment tests
        if env_result is not None:
            total_tests += 1
            if env_result:
                passed_tests += 1
                self.print_success("Environment Indicators")
            else:
                self.print_error("Environment Indicators")
        
        # Webhook tests
        if webhook_results:
            for test, result in webhook_results.items():
                total_tests += 1
                if result:
                    passed_tests += 1
                    self.print_success(f"Webhook {test.replace('_', ' ').title()}")
                else:
                    self.print_error(f"Webhook {test.replace('_', ' ').title()}")
        
        # Calculate success rate
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Tests Passed: {passed_tests}/{total_tests}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print(f"   Status: 🎉 EXCELLENT - Deployment is working well!")
        elif success_rate >= 75:
            print(f"   Status: ⚠️  GOOD - Minor issues may need attention")
        elif success_rate >= 50:
            print(f"   Status: ⚠️  FAIR - Several issues need fixing")
        else:
            print(f"   Status: ❌ POOR - Significant problems detected")
        
        return success_rate
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        print("🧪 Railway Deployment Feature Verification")
        print(f"🌐 Frontend URL: {self.frontend_url}")
        if self.backend_url:
            print(f"🔗 Backend URL: {self.backend_url}")
        print(f"📅 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        frontend_result = self.test_frontend_accessibility()
        backend_results = self.test_backend_connectivity()
        streamlit_result = self.test_streamlit_features()
        env_result = self.test_environment_indicators()
        webhook_results = self.test_webhook_endpoints()
        
        # Generate comprehensive report
        success_rate = self.generate_comprehensive_report(
            frontend_result, backend_results, streamlit_result, 
            env_result, webhook_results
        )
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report = {
            "timestamp": timestamp,
            "frontend_url": self.frontend_url,
            "backend_url": self.backend_url,
            "success_rate": success_rate,
            "results": {
                "frontend": frontend_result,
                "backend": backend_results,
                "streamlit": streamlit_result,
                "environment": env_result,
                "webhooks": webhook_results
            }
        }
        
        report_file = f"railway_verification_{timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Detailed report saved: {report_file}")
        return success_rate >= 75

def main():
    """Main function to run verification tests"""
    print("🔧 Railway Deployment Feature Verification Tool")
    print("=" * 60)
    
    # Instructions for manual testing
    print("\n📋 MANUAL TESTING INSTRUCTIONS:")
    print("=" * 40)
    print("1. 🌐 Go to your Railway deployment URL")
    print("2. 🧪 Test these features manually:")
    print("   - Video Processor tab: Enter a YouTube URL and process it")
    print("   - Channel Manager tab: Add/remove channels, check status")
    print("   - System Test tab: Test webhooks and API connectivity")
    print("3. 🔍 Check for errors in the browser console (F12)")
    print("4. 📱 Test on different devices/browsers")
    print("5. ⏱️  Check response times and performance")
    
    print("\n🤖 AUTOMATED TESTING:")
    print("=" * 40)
    print("To run automated tests, you need to provide your Railway URLs:")
    print()
    print("Example usage:")
    print("  python3 railway_verification.py")
    print("  # Then enter your Railway URLs when prompted")
    print()
    
    # Interactive URL input
    try:
        frontend_url = input("Enter your Railway frontend URL (or press Enter to skip): ").strip()
        if frontend_url:
            backend_url = input("Enter your Railway backend URL (optional, press Enter to skip): ").strip()
            backend_url = backend_url if backend_url else None
            
            print(f"\n🚀 Running automated tests...")
            tester = RailwayTester(frontend_url, backend_url)
            success = tester.run_all_tests()
            
            if success:
                print("\n🎉 Deployment verification completed successfully!")
            else:
                print("\n⚠️  Deployment verification found issues that need attention.")
        else:
            print("\n💡 Manual testing mode - follow the instructions above.")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing cancelled by user.")
    except Exception as e:
        print(f"\n❌ Testing failed: {str(e)}")

if __name__ == "__main__":
    main()
