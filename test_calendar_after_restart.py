#!/usr/bin/env python3
"""
Test script to verify Google Calendar integration after Railway restart.
Run this after forcing Railway restart to confirm calendar is working.
"""

import requests
import json

RAILWAY_URL = "https://helpful-solace-production.up.railway.app"

def test_calendar_status():
    """Check if calendar integration is working"""
    print("🔍 Testing Calendar Status...")
    
    try:
        response = requests.get(f"{RAILWAY_URL}/debug/calendar-status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Calendar Status Retrieved")
            print(f"   Mode: {data.get('mode_hint', 'unknown')}")
            print(f"   Enabled: {data.get('enabled', False)}")
            print(f"   Has Access Token: {data.get('has_access_token', False)}")
            print(f"   Has Refresh Token: {data.get('has_refresh_token', False)}")
            return data.get('mode_hint') == 'real_google_api'
        else:
            print(f"❌ Error checking status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to check calendar status: {e}")
        return False

def test_calendar_event_creation():
    """Test creating a calendar event"""
    print("\n📅 Testing Calendar Event Creation...")
    
    try:
        response = requests.post(f"{RAILWAY_URL}/test/create-calendar-event")
        if response.status_code == 200:
            data = response.json()
            if data.get('mock_mode'):
                print("❌ Still in mock mode")
                return False
            else:
                print("✅ Real calendar event created!")
                print(f"   Event ID: {data.get('event_id', 'N/A')}")
                return True
        else:
            print(f"❌ Error creating event: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to create calendar event: {e}")
        return False

def main():
    print("🧪 Post-Restart Calendar Integration Test")
    print("=" * 50)
    
    # Test calendar status
    status_ok = test_calendar_status()
    
    # Test event creation
    event_ok = test_calendar_event_creation()
    
    print("\n📊 Results:")
    print("=" * 20)
    
    if status_ok and event_ok:
        print("🎉 SUCCESS: Calendar integration is working!")
        print("   Real Google Calendar events will now be created")
    elif status_ok and not event_ok:
        print("⚠️  PARTIAL: Status shows real mode but event creation failed")
        print("   May need a few more minutes for full initialization")
    else:
        print("❌ ISSUE: Calendar still in mock mode")
        print("   Try waiting 2-3 more minutes and run again")
        print("   Or check Railway logs for errors")

if __name__ == "__main__":
    main()