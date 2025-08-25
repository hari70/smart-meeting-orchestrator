#!/usr/bin/env python3
"""
Test script to verify LLM integration on Railway deployment
"""

import requests
import json

def test_llm_integration():
    """Test if LLM integration is working on Railway"""
    
    railway_url = "https://smart-meeting-orchestrator-production-up.railway.app"
    
    print("🧠 Testing LLM Integration on Railway")
    print("=" * 40)
    
    # Test payload for scheduling request
    test_payload = {
        "type": "message.received",
        "data": {
            "body": "schedule a meeting with Rick tomorrow at 11am",
            "conversation": {
                "contact": {
                    "first_name": "Test",
                    "last_name": "User",
                    "phone_number": "+12345678900"
                }
            }
        }
    }
    
    try:
        print(f"🚀 Sending test SMS to: {railway_url}/webhook/sms")
        print(f"📝 Message: '{test_payload['data']['body']}'")
        
        response = requests.post(
            f"{railway_url}/webhook/sms",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=30
        )
        
        print(f"\n📨 Response Status: {response.status_code}")
        print(f"📨 Response Body: {response.text}")
        
        # Analyze response
        if response.status_code == 200:
            if "LLM unavailable" in response.text or "LLM temporarily unavailable" in response.text:
                print("\n❌ LLM NOT WORKING:")
                print("   - ANTHROPIC_API_KEY is missing or incorrect in Railway")
                print("   - System is using fallback mode")
                print("\n💡 SOLUTION:")
                print("   1. Go to Railway Dashboard → Variables")
                print("   2. Add/fix: ANTHROPIC_API_KEY=sk-ant-api03-...")
                print("   3. Redeploy and test again")
                return False
            else:
                print("\n✅ LLM WORKING:")
                print("   - Anthropic integration is functional")
                print("   - Getting AI-powered responses")
                return True
        else:
            print(f"\n⚠️ Unexpected response code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error testing LLM: {e}")
        return False

if __name__ == "__main__":
    test_llm_integration()