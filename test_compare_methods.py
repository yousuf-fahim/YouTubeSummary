#!/usr/bin/env python3
"""
Test the main get_transcript vs direct _get_transcript_from_api
"""
import asyncio
import sys
import os

# Add the current directory to the path so we can import shared modules
sys.path.append(os.path.dirname(__file__))

async def test_main_function():
    print("Testing the main get_transcript function...")
    
    from shared.transcript import get_transcript
    
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        result = await get_transcript(video_url)
        print(f"Main function result: {len(result) if result else 0} characters")
        if result:
            print(f"First 100 chars: {result[:100]}")
        return result
    except Exception as e:
        print(f"Main function error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_direct_function():
    print("Testing the direct _get_transcript_from_api function...")
    
    from shared.transcript import _get_transcript_from_api
    
    video_id = "dQw4w9WgXcQ"
    
    try:
        result = _get_transcript_from_api(video_id)
        print(f"Direct function result: {len(result) if result else 0} characters")
        if result:
            print(f"First 100 chars: {result[:100]}")
        return result
    except Exception as e:
        print(f"Direct function error: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    print("=== Comparing transcript extraction approaches ===\n")
    
    # Test 1: Direct function (what frontend uses)
    direct_result = test_direct_function()
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Main async function (what backend uses)
    main_result = await test_main_function()
    
    print("\n" + "="*50 + "\n")
    
    # Compare results
    print("COMPARISON:")
    print(f"Direct function: {'✅ SUCCESS' if direct_result else '❌ FAILED'}")
    print(f"Main function: {'✅ SUCCESS' if main_result else '❌ FAILED'}")
    
    if direct_result and main_result:
        print(f"Both worked! Lengths: Direct={len(direct_result)}, Main={len(main_result)}")
    elif direct_result and not main_result:
        print("❌ Main function failing while direct function works - this is the issue!")
    elif not direct_result and main_result:
        print("❌ Direct function failing while main function works - unexpected!")
    else:
        print("❌ Both functions failing")

if __name__ == "__main__":
    asyncio.run(main())
