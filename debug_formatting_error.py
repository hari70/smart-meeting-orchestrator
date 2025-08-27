#!/usr/bin/env python3
"""
Debug script to identify exactly where the f-string formatting error occurs.
"""

import requests
import json
import time

RAILWAY_URL = "https://helpful-solace-production.up.railway.app"

def test_step_by_step():
    """Test each step that could trigger the formatting error"""
    print("🔍 DEBUGGING F-STRING FORMATTING ERROR")
    print("=" * 50)
    
    # Test 1: Basic LLM with simple message (no tools)
    print("1. Testing simple LLM call (no tools expected)...")
    try:
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-response",
            json={"message": "hello there"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            llm_response = data.get('llm_response', '')
            is_fallback = 'LLM' in llm_response and ('unavailable' in llm_response or 'fallback' in llm_response)
            print(f"   ✅ Status: {data.get('success', False)}")
            print(f"   ✅ Is Fallback: {is_fallback}")
            print(f"   ✅ Response: {llm_response[:60]}...")
            
            if is_fallback:
                print("   ❌ EVEN SIMPLE MESSAGES FAIL - Error occurs early in LLM chain")
            else:
                print("   ✅ Simple messages work - Error occurs with tool usage")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 2: Scheduling request that should trigger tools
    print("\n2. Testing scheduling request (should trigger tools)...")
    try:
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-response",
            json={"message": "Schedule a meeting with Rick tomorrow at 11am for Cyber project review"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            llm_response = data.get('llm_response', '')
            is_fallback = 'LLM' in llm_response and ('unavailable' in llm_response or 'fallback' in llm_response)
            print(f"   ✅ Status: {data.get('success', False)}")
            print(f"   ✅ Is Fallback: {is_fallback}")
            print(f"   ✅ Response: {llm_response[:60]}...")
            
            if is_fallback:
                print("   ❌ SCHEDULING REQUESTS FAIL - Error likely in tool processing")
            else:
                print("   ✅ Scheduling works!")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 3: Direct tool calling test
    print("\n3. Testing direct tool calling capability...")
    try:
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-tools-debug",
            json={"message": "test tool calling"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Tool calling works: {data.get('tool_calling_works', False)}")
            if not data.get('tool_calling_works'):
                print(f"   ❌ Tool error: {data.get('error_in_tool_call', 'unknown')}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 4: Webhook simulation (closest to real usage)
    print("\n4. Testing webhook simulation (closest to real SMS flow)...")
    try:
        webhook_payload = {
            "type": "message.received",
            "data": {
                "body": "Schedule a meeting with Rick tomorrow at 11am for Cyber project review",
                "conversation": {
                    "contact": {
                        "first_name": "Test",
                        "last_name": "User",
                        "phone_number": "+12408029592"  # Your real phone
                    }
                }
            }
        }
        
        response = requests.post(
            f"{RAILWAY_URL}/webhook/sms",
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"   ✅ Webhook Status: {response.status_code}")
        print(f"   ✅ Response: {response.text}")
        
        if "processed" in response.text:
            print("   ✅ Webhook processed - Check SMS or Railway logs for actual error")
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")

def main():
    print("🕵️ F-String Formatting Error Diagnostic")
    print("=" * 45)
    print("This will help us pinpoint exactly where the error occurs.")
    print()
    
    test_step_by_step()
    
    print("\n📊 ANALYSIS:")
    print("=" * 20)
    print("Based on the test results:")
    print("- If test 1 fails: Error is in basic LLM initialization/setup")
    print("- If test 1 works but test 2 fails: Error is in tool processing")
    print("- If tests 1-3 work but test 4 fails: Error is in webhook flow")
    print()
    print("💡 NEXT STEPS:")
    print("1. Check Railway logs immediately after running this script")
    print("2. Look for 'Invalid format specifier' error messages")
    print("3. The error will show exactly which line is causing the issue")

if __name__ == "__main__":
    main()