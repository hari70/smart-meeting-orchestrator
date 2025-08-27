#!/usr/bin/env python3
"""
Test Anthropic API on Railway deployment to diagnose LLM issues.
"""

import requests
import json

RAILWAY_URL = "https://helpful-solace-production.up.railway.app"

def test_railway_anthropic():
    """Test Anthropic API directly on Railway"""
    print("🧪 Testing Anthropic API on Railway")
    print("=" * 40)
    
    try:
        # Test the LLM response endpoint with detailed error info
        response = requests.post(
            f"{RAILWAY_URL}/test/llm-response",
            json={"message": "test api connection", "debug": True},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            
            # Check if it's actually using LLM or fallback
            llm_response = data.get("llm_response", "")
            if "LLM unavailable" in llm_response or "fallback" in llm_response:
                print("\n❌ LLM is falling back to basic processing")
                print("   This indicates an error in the Anthropic API call on Railway")
            else:
                print("\n✅ LLM is working correctly")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

def check_railway_environment():
    """Check Railway environment variables"""
    print("\n🔍 Checking Railway Environment")
    print("=" * 35)
    
    try:
        response = requests.get(f"{RAILWAY_URL}/test/environment-check")
        
        if response.status_code == 200:
            data = response.json()
            env_status = data.get("environment_status", {})
            
            print("Environment Variables:")
            for key, value in env_status.items():
                if "ANTHROPIC" in key:
                    print(f"  {key}: {value}")
        else:
            print(f"❌ Could not check environment: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Environment check failed: {e}")

def simulate_sms_request():
    """Simulate the actual SMS flow to see detailed error"""
    print("\n📱 Simulating SMS Request")
    print("=" * 30)
    
    try:
        # Simulate the webhook payload
        payload = {
            "from": "+15551234567",  # Test phone
            "body": "Schedule a meeting with John tomorrow at 3pm for project review"
        }
        
        response = requests.post(
            f"{RAILWAY_URL}/webhook/sms",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Webhook Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ SMS simulation failed: {e}")

def main():
    print("🚂 Railway LLM Integration Test")
    print("=" * 35)
    
    # Check environment first
    check_railway_environment()
    
    # Test direct LLM endpoint
    test_railway_anthropic()
    
    # Test full SMS flow
    simulate_sms_request()

if __name__ == "__main__":
    main()