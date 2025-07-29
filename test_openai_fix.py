#!/usr/bin/env python3
"""
Test script to verify OpenAI API integration is working with the new tools format
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from shared.summarize import generate_summary

async def test_openai_integration():
    """Test the OpenAI API integration with a simple transcript"""
    
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ No OpenAI API key found in environment variables")
        return False
    
    print("✅ OpenAI API key found")
    
    # Test transcript
    test_transcript = """
    Hello everyone, welcome to this test video. Today we're going to talk about 
    artificial intelligence and its impact on modern technology. AI has revolutionized 
    many industries including healthcare, finance, and education. The key benefits 
    include automation, improved efficiency, and better decision making. Some important 
    companies in this space include OpenAI, Google, and Microsoft. In conclusion, 
    AI will continue to shape the future of technology.
    """
    
    try:
        print("🔄 Testing OpenAI API call with new tools format...")
        result = await generate_summary(test_transcript, api_key)
        
        if result and isinstance(result, dict):
            print("✅ OpenAI API call successful!")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"Summary: {result.get('summary', 'N/A')[:100]}...")
            print(f"Points: {len(result.get('points', []))} points")
            print(f"Verdict: {result.get('verdict', 'N/A')}")
            return True
        else:
            print("❌ OpenAI API call failed - no valid result returned")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI API call failed with error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing OpenAI API Integration")
    print("=" * 50)
    
    # Run the async test
    success = asyncio.run(test_openai_integration())
    
    if success:
        print("\n✅ All tests passed! OpenAI integration is working correctly.")
    else:
        print("\n❌ Tests failed! Please check the OpenAI API configuration.")
