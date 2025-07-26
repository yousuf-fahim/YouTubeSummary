#!/usr/bin/env python3
"""
Migration script to move configuration from JSON files to environment variables.
This script helps transition from the old JSON-based config to the new secure system.
"""
import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def create_env_file():
    """Create .env file from existing config.json if needed"""
    print("🔒 Security Migration: Moving from JSON config to environment variables")
    
    # Check if config.json exists in any location
    config_paths = [
        'backend/data/config.json',
        'frontend/data/config.json', 
        'shared/data/config.json',
        'data/config.json'
    ]
    
    config_data = None
    config_file_found = None
    
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config_data = json.load(f)
                    config_file_found = path
                    print(f"📁 Found config file: {path}")
                    break
            except Exception as e:
                print(f"❌ Error reading {path}: {e}")
    
    if not config_data:
        print("✅ No config.json files found. Environment variables should be used.")
        return
    
    # Show what was found
    print(f"\n🔍 Config data found:")
    print(f"   - OpenAI API Key: {'✓' if config_data.get('openai_api_key') else '✗'}")
    print(f"   - Discord Webhooks: {len(config_data.get('webhooks', {}))}")
    print(f"   - Webhook Auth Token: {'✓' if config_data.get('webhook_auth_token') else '✗'}")
    print(f"   - Prompts: {len(config_data.get('prompts', {}))}")
    
    # Check if .env already exists
    if os.path.exists('.env'):
        print(f"\n✅ .env file already exists. Manual verification recommended.")
        print(f"🔒 Sensitive data from {config_file_found} should be moved to .env")
        print(f"🗑️  You can safely delete {config_file_found} after verification")
    else:
        print(f"\n📝 .env file needs to be created with sensitive data from {config_file_found}")
    
    # Security recommendations
    print(f"\n🛡️  Security Recommendations:")
    print(f"   1. Verify all sensitive data is in .env file")
    print(f"   2. Delete JSON config files: {config_file_found}")
    print(f"   3. Ensure .env is in .gitignore (already done)")
    print(f"   4. Use environment variables in production (Heroku config vars)")

def verify_security():
    """Verify that sensitive data is not in git"""
    print(f"\n🔍 Security Verification:")
    
    # Check if sensitive files are still tracked by git
    try:
        import subprocess
        result = subprocess.run(['git', 'ls-files', '**/*config.json'], 
                              capture_output=True, text=True, cwd='.')
        tracked_configs = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        if tracked_configs and tracked_configs[0]:
            print(f"⚠️  WARNING: Config files still tracked by git:")
            for file in tracked_configs:
                if file:
                    print(f"   - {file}")
            print(f"   Run: git rm --cached <file> to untrack them")
        else:
            print(f"✅ No config.json files tracked by git")
            
    except Exception as e:
        print(f"❌ Could not check git status: {e}")
    
    # Check .gitignore
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            gitignore_content = f.read()
        
        sensitive_patterns = ['*.env', 'config.json', '*secrets*']
        missing_patterns = []
        
        for pattern in sensitive_patterns:
            if pattern not in gitignore_content:
                missing_patterns.append(pattern)
        
        if missing_patterns:
            print(f"⚠️  Missing .gitignore patterns: {missing_patterns}")
        else:
            print(f"✅ .gitignore properly configured for sensitive files")
    
    # Check if .env exists
    if os.path.exists('.env'):
        print(f"✅ .env file exists")
    else:
        print(f"⚠️  .env file not found - create one with your sensitive data")

if __name__ == "__main__":
    create_env_file()
    verify_security()
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Verify your .env file has all required values")
    print(f"   2. Delete any remaining config.json files")
    print(f"   3. Test your application locally")
    print(f"   4. Proceed with GitHub and deployment")
