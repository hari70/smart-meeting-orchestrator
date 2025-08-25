#!/usr/bin/env python3
"""
Comprehensive Deployment Issues Diagnostic and Fix Script
Addresses both LLM integration and Google Calendar problems
"""

import os
import sys
import requests
import json
import logging
from datetime import datetime

def check_railway_deployment():
    """Check various potential Railway URLs"""
    potential_urls = [
        "https://smart-meeting-orchestrator-production.up.railway.app",
        "https://smart-meeting-orchestrator.up.railway.app", 
        "https://smart-meeting-orchestrator-production-up.railway.app",
        "https://smart-meeting-orchestrator-hari70.up.railway.app"
    ]
    
    print("🚂 Railway Deployment Check:")
    print("=" * 40)
    
    working_url = None
    for url in potential_urls:
        try:
            print(f"Testing: {url}")
            response = requests.get(f"{url}/health", timeout=10)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:100]}...")
            
            if response.status_code == 200:
                working_url = url
                print(f"  ✅ FOUND WORKING URL: {url}")
                break
            else:
                print(f"  ❌ Not working")
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:50]}...")
    
    return working_url

def test_llm_on_railway(railway_url):
    """Test LLM integration on Railway deployment"""
    if not railway_url:
        print("❌ No working Railway URL found")
        return False
    
    print(f"\n🧠 LLM Integration Test on Railway:")
    print("=" * 40)
    
    # Test SMS webhook that should trigger LLM
    test_payload = {
        "type": "message.received",
        "data": {
            "body": "schedule a meeting with John tomorrow at 2pm",
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
        print(f"🚀 Testing LLM via SMS webhook...")
        print(f"URL: {railway_url}/webhook/sms")
        print(f"Payload: {json.dumps(test_payload, indent=2)}")
        
        response = requests.post(
            f"{railway_url}/webhook/sms",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=30
        )
        
        print(f"📨 Response Status: {response.status_code}")
        print(f"📨 Response Body: {response.text}")
        
        if "LLM unavailable" in response.text:
            print("❌ LLM is not working - shows fallback mode")
            return False
        elif response.status_code == 200:
            print("✅ LLM appears to be working")
            return True
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing LLM: {e}")
        return False

def diagnose_google_calendar():
    """Diagnose Google Calendar setup"""
    print(f"\n📅 Google Calendar Integration Diagnosis:")
    print("=" * 40)
    
    # Check environment variables
    calendar_vars = {
        "GOOGLE_CALENDAR_ACCESS_TOKEN": os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN"),
        "GOOGLE_CALENDAR_REFRESH_TOKEN": os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"),
        "GOOGLE_CALENDAR_CLIENT_ID": os.getenv("GOOGLE_CALENDAR_CLIENT_ID"),
        "GOOGLE_CALENDAR_CLIENT_SECRET": os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET"),
        "GOOGLE_CALENDAR_ID": os.getenv("GOOGLE_CALENDAR_ID", "primary")
    }
    
    for var, value in calendar_vars.items():
        status = "✅ SET" if value else "❌ NOT SET"
        preview = f" ({value[:20]}...)" if value and len(value) > 20 else ""
        print(f"{var}: {status}{preview}")
    
    # Determine integration status
    has_access_token = bool(calendar_vars["GOOGLE_CALENDAR_ACCESS_TOKEN"])
    has_refresh_setup = all([
        calendar_vars["GOOGLE_CALENDAR_REFRESH_TOKEN"],
        calendar_vars["GOOGLE_CALENDAR_CLIENT_ID"], 
        calendar_vars["GOOGLE_CALENDAR_CLIENT_SECRET"]
    ])
    
    print(f"\n📊 Calendar Status:")
    if has_access_token:
        print("✅ Direct access token available")
        return "direct_token"
    elif has_refresh_setup:
        print("✅ Refresh token setup available")
        return "refresh_token"
    else:
        print("❌ No Google Calendar credentials configured")
        print("📝 Calendar will run in MOCK MODE")
        return "mock_mode"

def test_calendar_creation(railway_url):
    """Test calendar event creation"""
    if not railway_url:
        return False
    
    print(f"\n📅 Calendar Event Creation Test:")
    print("=" * 40)
    
    test_payload = {
        "title": "Test Event from Diagnostic",
        "hours_from_now": 2,
        "duration_minutes": 30
    }
    
    try:
        print(f"🚀 Testing calendar creation...")
        response = requests.post(
            f"{railway_url}/test/create-calendar-event",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=30
        )
        
        print(f"📨 Response Status: {response.status_code}")
        print(f"📨 Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("source") == "mock":
                print("⚠️ Calendar creation working but in MOCK MODE")
                return "mock"
            else:
                print("✅ Real calendar event created!")
                return "real"
        else:
            print(f"❌ Calendar creation failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing calendar: {e}")
        return False

def provide_solutions(llm_working, calendar_status, railway_url):
    """Provide specific solutions based on diagnosis"""
    print(f"\n🛠️ SOLUTIONS:")
    print("=" * 50)
    
    # LLM Solutions
    if not llm_working:
        print("❌ LLM ISSUE: Anthropic integration not working on Railway")
        print("\n💡 LLM SOLUTION:")
        print("1. Go to Railway Dashboard → Your Project → Variables")
        print("2. Verify ANTHROPIC_API_KEY is set correctly:")
        print("   Value should start with: sk-ant-api03-...")
        print("3. Check for typos in the variable name")
        print("4. Redeploy after adding/fixing the variable")
        print("5. Test by sending SMS: 'schedule meeting tomorrow at 2pm'")
    else:
        print("✅ LLM working correctly")
    
    # Google Calendar Solutions
    if calendar_status == "mock_mode":
        print("\n❌ GOOGLE CALENDAR ISSUE: Running in mock mode")
        print("\n💡 GOOGLE CALENDAR SOLUTION:")
        print("Choose ONE of these options:")
        print("\nOption A - Quick Access Token (temporary):")
        print("1. Go to: https://developers.google.com/oauthplayground/")
        print("2. Select 'Google Calendar API v3' scope")
        print("3. Authorize and get access_token")
        print("4. Add to Railway: GOOGLE_CALENDAR_ACCESS_TOKEN=ya29....")
        
        print("\nOption B - Refresh Token (permanent):")
        print("1. Create OAuth2 credentials in Google Cloud Console")
        print("2. Use OAuth playground to get refresh_token")
        print("3. Add to Railway:")
        print("   GOOGLE_CALENDAR_REFRESH_TOKEN=1//...")
        print("   GOOGLE_CALENDAR_CLIENT_ID=...apps.googleusercontent.com")
        print("   GOOGLE_CALENDAR_CLIENT_SECRET=...")
        
        print("\nOption C - Service Account:")
        print("1. Create service account in Google Cloud Console")
        print("2. Download JSON key and convert to environment variables")
        print("3. Share calendar with service account email")
        
    elif calendar_status == "refresh_token":
        print("✅ Google Calendar refresh token setup detected")
        print("💡 If calendar still not working, check token validity")
    elif calendar_status == "direct_token":
        print("✅ Google Calendar direct token setup detected")
        print("💡 Token may expire - consider refresh token setup")
    
    # General info
    if railway_url:
        print(f"\n🌐 Your Railway URL: {railway_url}")
        print(f"📚 API Docs: {railway_url}/docs")
        print(f"🧪 Test endpoint: {railway_url}/test/create-calendar-event")

def main():
    """Run complete diagnostic and provide solutions"""
    print("🔍 Smart Meeting Orchestrator - Deployment Issues Diagnostic")
    print("=" * 65)
    print(f"Diagnostic run at: {datetime.now()}")
    
    # 1. Find Railway deployment
    railway_url = check_railway_deployment()
    
    # 2. Test LLM integration
    llm_working = test_llm_on_railway(railway_url) if railway_url else False
    
    # 3. Check Google Calendar setup
    calendar_status = diagnose_google_calendar()
    
    # 4. Test calendar creation if Railway is working
    calendar_working = test_calendar_creation(railway_url) if railway_url else False
    
    # 5. Provide solutions
    provide_solutions(llm_working, calendar_status, railway_url)
    
    # 6. Summary
    print(f"\n📊 DIAGNOSTIC SUMMARY:")
    print("=" * 50)
    print(f"Railway Deployment: {'✅ Found' if railway_url else '❌ Not Found'}")
    print(f"LLM Integration: {'✅ Working' if llm_working else '❌ Not Working'}")
    print(f"Calendar Setup: {calendar_status}")
    print(f"Calendar Creation: {'✅ Working' if calendar_working else '❌ Issues'}")
    
    if railway_url and llm_working and calendar_working == "real":
        print("\n🎉 ALL SYSTEMS WORKING! Your SMS bot should be fully functional.")
    else:
        print(f"\n⚠️ ISSUES FOUND - Follow solutions above to fix:")
        if not railway_url:
            print("  • Find your Railway deployment URL")
        if not llm_working:
            print("  • Fix ANTHROPIC_API_KEY in Railway")
        if calendar_status == "mock_mode":
            print("  • Set up Google Calendar API credentials")

if __name__ == "__main__":
    main()