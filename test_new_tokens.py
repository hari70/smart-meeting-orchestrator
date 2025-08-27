#!/usr/bin/env python3
"""Quick test script for new Google Calendar tokens"""

import requests
import json

def test_calendar_integration():
    """Test if the new tokens work"""
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("🧪 Testing Updated Google Calendar Integration")
    print("=" * 45)
    
    # Test 1: Environment check
    print("1. Checking environment variables...")
    try:
        response = requests.get(f"{railway_url}/test/environment-check", timeout=10)
        if response.status_code == 200:
            env_data = response.json()
            env_vars = env_data.get('environment_status', {})
            
            access_token = env_vars.get('GOOGLE_CALENDAR_ACCESS_TOKEN', 'NOT_SET')
            refresh_token = env_vars.get('GOOGLE_CALENDAR_REFRESH_TOKEN', 'NOT_SET')
            
            print(f"   Access Token: {access_token}")
            print(f"   Refresh Token: {refresh_token}")
            
            if access_token != 'NOT_SET' and refresh_token != 'NOT_SET':
                print("   ✅ Tokens are set in Railway")
            else:
                print("   ❌ Tokens missing - update Railway variables")
                return
        else:
            print(f"   ❌ Environment check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Test 2: Calendar functionality
    print("\n2. Testing calendar event creation...")
    try:
        test_data = {
            "title": "🧪 Token Refresh Test",
            "hours_from_now": 2,
            "duration_minutes": 30
        }
        
        response = requests.post(
            f"{railway_url}/test/create-calendar-event",
            json=test_data,
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            integration_type = result.get('integration_type', 'unknown')
            google_working = result.get('google_calendar_working', False)
            
            print(f"   Integration Type: {integration_type}")
            print(f"   Google Calendar Working: {google_working}")
            
            if google_working and integration_type == 'real_google_api':
                print("   ✅ SUCCESS! Real Google Calendar integration is working!")
                
                event_details = result.get('event_details', {})
                calendar_link = event_details.get('calendar_link', '')
                meet_link = event_details.get('meet_link', '')
                
                print(f"   📅 Event created: {event_details.get('title', 'Unknown')}")
                print(f"   🔗 Calendar: {calendar_link}")
                print(f"   📞 Meet Link: {meet_link}")
                
            elif integration_type == 'mock_mode':
                print("   ❌ Still in mock mode - tokens may be invalid")
                print("   💡 Check that tokens were copied correctly")
                
            else:
                print(f"   ⚠️ Unexpected result: {result}")
                
        else:
            print(f"   ❌ Calendar test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n📱 Next step: Test via SMS!")
    print("Send SMS: 'Schedule test meeting tomorrow at 2pm'")
    print("Should create a REAL Google Calendar event!")

if __name__ == "__main__":
    test_calendar_integration()