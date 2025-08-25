#!/usr/bin/env python3
"""
Test script for your specific Railway deployment
URL: https://helpful-solace-production.up.railway.app/
"""

import requests
import json

def test_your_railway_deployment():
    """Test your specific Railway deployment"""
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("🚂 Testing Your Railway Deployment")
    print("=" * 45)
    print(f"URL: {railway_url}")
    print()
    
    # Test 1: Health Check
    print("1. 🏥 Health Check Test")
    print("-" * 30)
    try:
        response = requests.get(f"{railway_url}/health", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check PASSED - FastAPI app is running!")
            health_working = True
        else:
            print("❌ Health check FAILED")
            health_working = False
    except Exception as e:
        print(f"❌ Health check ERROR: {e}")
        health_working = False
    
    print()
    
    # Test 2: Root Endpoint
    print("2. 🏠 Root Endpoint Test")
    print("-" * 30)
    try:
        response = requests.get(f"{railway_url}/", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if "Smart Meeting Orchestrator" in response.text:
            print("✅ Root endpoint PASSED - App properly identified!")
            root_working = True
        else:
            print("❌ Root endpoint shows unexpected content")
            root_working = False
    except Exception as e:
        print(f"❌ Root endpoint ERROR: {e}")
        root_working = False
    
    print()
    
    # Test 3: SMS Webhook
    print("3. 📱 SMS Webhook Test")
    print("-" * 30)
    
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
        print(f"Sending SMS webhook to: {railway_url}/webhook/sms")
        response = requests.post(
            f"{railway_url}/webhook/sms",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            if "LLM unavailable" in response.text:
                print("⚠️ Webhook working but LLM NOT CONFIGURED")
                print("   → ANTHROPIC_API_KEY missing in Railway variables")
                webhook_working = "llm_missing"
            else:
                print("✅ Webhook working with full LLM integration!")
                webhook_working = True
        else:
            print("❌ Webhook FAILED")
            webhook_working = False
            
    except Exception as e:
        print(f"❌ Webhook ERROR: {e}")
        webhook_working = False
    
    print()
    
    # Test 4: API Documentation
    print("4. 📚 API Documentation Test")
    print("-" * 30)
    try:
        response = requests.get(f"{railway_url}/docs", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API docs accessible!")
            print(f"📖 View at: {railway_url}/docs")
            docs_working = True
        else:
            print("❌ API docs not accessible")
            docs_working = False
    except Exception as e:
        print(f"❌ API docs ERROR: {e}")
        docs_working = False
    
    print()
    
    # Summary and Solutions
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 45)
    print(f"Health Check: {'✅' if health_working else '❌'}")
    print(f"Root Endpoint: {'✅' if root_working else '❌'}")
    print(f"SMS Webhook: {'✅' if webhook_working == True else '⚠️ LLM Missing' if webhook_working == 'llm_missing' else '❌'}")
    print(f"API Docs: {'✅' if docs_working else '❌'}")
    
    print()
    print("🛠️ NEXT STEPS")
    print("=" * 30)
    
    if health_working and root_working:
        print("✅ Your FastAPI app is running correctly on Railway!")
        
        if webhook_working == "llm_missing":
            print()
            print("🔧 LLM INTEGRATION FIX NEEDED:")
            print("1. Go to Railway Dashboard → Variables")
            print("2. Add: ANTHROPIC_API_KEY=<your_anthropic_api_key_here>")
            print("3. Save and redeploy")
            print("4. Test again with SMS")
            
        elif webhook_working == True:
            print("🎉 EVERYTHING IS WORKING!")
            print("Your SMS bot should be fully functional.")
            
        else:
            print("⚠️ Webhook issues - check database connection and environment variables")
            
    else:
        print("❌ FastAPI app not running properly")
        print("Check Railway deployment logs for startup errors")
    
    print()
    print("📱 GOOGLE CALENDAR SETUP:")
    print("Your calendar integration is in mock mode.")
    print("To enable real calendar events, you need Google Calendar API credentials.")
    print("Would you like help setting up Google Calendar integration?")

if __name__ == "__main__":
    test_your_railway_deployment()