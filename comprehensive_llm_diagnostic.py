#!/usr/bin/env python3
"""
Comprehensive LLM diagnostic to identify remaining issues after the formatting fix.
"""

import requests
import json

RAILWAY_URL = "https://helpful-solace-production.up.railway.app"

def test_llm_step_by_step():
    """Test each step of the LLM integration to identify where it fails"""
    print("🔍 Testing LLM Integration Step by Step")
    print("=" * 50)
    
    # Test 1: Basic LLM connectivity
    print("1. Testing basic LLM functionality...")
    try:
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-debug",
            json={"message": "hello"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Basic API call: {data.get('success', False)}")
            print(f"   ✅ Anthropic version: {data.get('anthropic_version', 'unknown')}")
        else:
            print(f"   ❌ Basic test failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Basic test exception: {e}")
    
    # Test 2: Tool calling
    print("\\n2. Testing tool calling...")
    try:
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-tools-debug",
            json={"message": "test tools"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Tool calling works: {data.get('tool_calling_works', False)}")
            if not data.get('tool_calling_works'):
                print(f"   ❌ Tool error: {data.get('error_in_tool_call', 'unknown')}")
        else:
            print(f"   ❌ Tool test failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Tool test exception: {e}")
    
    # Test 3: Full LLM processing
    print("\\n3. Testing full LLM processing...")
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
            
            print(f"   ✅ LLM enabled: {data.get('llm_enabled', False)}")
            print(f"   ✅ Response success: {data.get('success', False)}")
            print(f"   ✅ Using fallback: {is_fallback}")
            print(f"   ✅ Response: {llm_response[:100]}...")
            
            if is_fallback:
                print("   🚨 ISSUE: Still using fallback - there's an error in LLM processing")
            else:
                print("   🎉 SUCCESS: Real LLM response detected!")
                
        else:
            print(f"   ❌ Full test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Full test exception: {e}")

def test_calendar_status():
    """Test calendar integration status"""
    print("\\n📅 Testing Calendar Integration")
    print("=" * 35)
    
    try:
        response = requests.get(f"{RAILWAY_URL}/test/calendar-status")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Calendar enabled: {data.get('calendar_integration_enabled', False)}")
            print(f"Calendar mode: {data.get('calendar_mode', 'unknown')}")
            
            creds = data.get('credentials_status', {})
            print(f"Has access token: {creds.get('has_access_token', False)}")
            print(f"Has refresh token: {creds.get('has_refresh_token', False)}")
            print(f"Status: {creds.get('recommended_setup', 'unknown')}")
        else:
            print(f"❌ Calendar check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Calendar check exception: {e}")

def main():
    print("🧪 Comprehensive LLM Diagnostic")
    print("=" * 40)
    print("Testing after the f-string formatting fix...")
    print()
    
    test_llm_step_by_step()
    test_calendar_status()
    
    print("\\n📊 Summary:")
    print("=" * 20)
    print("If step 1 & 2 pass but step 3 still shows fallback,")
    print("there's likely another error in the LLM processing chain.")
    print("Check Railway logs for specific error messages.")

if __name__ == "__main__":
    main()