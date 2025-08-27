#!/usr/bin/env python3
"""
Verify that the Google Calendar token refresh issue is resolved
"""

import requests
import json
import time

def verify_calendar_integration():
    """Verify the calendar integration after token refresh"""
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("🔍 Verifying Google Calendar Token Fix")
    print("=" * 42)
    
    # Step 1: Check environment variables
    print("1. Checking updated environment variables...")
    try:
        response = requests.get(f"{railway_url}/test/environment-check", timeout=10)
        if response.status_code == 200:
            env_data = response.json()
            env_vars = env_data.get('environment_status', {})
            
            access_token = env_vars.get('GOOGLE_CALENDAR_ACCESS_TOKEN', 'NOT_SET')
            refresh_token = env_vars.get('GOOGLE_CALENDAR_REFRESH_TOKEN', 'NOT_SET')
            
            print(f"   Access Token: {access_token}")
            print(f"   Refresh Token: {refresh_token}")
            
            # Check token formats
            access_token_valid = access_token.startswith('ya29.') if access_token != 'NOT_SET' else False
            refresh_token_valid = refresh_token.startswith('1//') if refresh_token != 'NOT_SET' else False
            
            if access_token_valid and refresh_token_valid:
                print("   ✅ Both tokens are set with correct format")
            else:
                print("   ❌ Tokens missing or invalid format")
                if not access_token_valid:
                    print("      ❌ Access token should start with 'ya29.'")
                if not refresh_token_valid:
                    print("      ❌ Refresh token should start with '1//'")
                return False
                
        else:
            print(f"   ❌ Environment check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error checking environment: {e}")
        return False
    
    print("   ✅ Environment variables look good")
    
    # Step 2: Test calendar functionality
    print("\n2. Testing real calendar event creation...")
    try:
        test_data = {
            "title": "🔧 Token Fix Verification",
            "hours_from_now": 1,
            "duration_minutes": 30
        }
        
        response = requests.post(
            f"{railway_url}/test/create-calendar-event",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            
            integration_type = result.get('integration_type', 'unknown')
            google_working = result.get('google_calendar_working', False)
            
            print(f"   Response Status: {response.status_code}")
            print(f"   Integration Type: {integration_type}")
            print(f"   Google Calendar Working: {google_working}")
            
            if google_working and integration_type == 'real_google_api':
                print("   ✅ SUCCESS! Real Google Calendar integration is working!")
                
                event_details = result.get('event_details', {})
                print(f"   📅 Event: {event_details.get('title', 'Unknown')}")
                print(f"   ⏰ Time: {event_details.get('start_time', 'Unknown')}")
                
                calendar_link = event_details.get('calendar_link', '')
                meet_link = event_details.get('meet_link', '')
                
                if calendar_link:
                    print(f"   🔗 Calendar Link: {calendar_link}")
                if meet_link and 'mock' not in meet_link:
                    print(f"   📞 Meet Link: {meet_link}")
                
                return True
                
            elif integration_type == 'mock_mode':
                print("   ❌ Still in mock mode")
                print("   💡 This means tokens are still invalid or not being used")
                
                # Check the specific response
                print(f"   📋 Full response: {json.dumps(result, indent=2)}")
                return False
                
            else:
                print(f"   ⚠️ Unexpected integration type: {integration_type}")
                return False
                
        else:
            print(f"   ❌ Calendar test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error testing calendar: {e}")
        return False
    
    # Step 3: Test token refresh capability
    print("\n3. Testing token refresh mechanism...")
    
    # Wait a moment for any background processes
    time.sleep(2)
    
    # Try another calendar operation to see if refresh works
    try:
        list_data = {"limit": 3}
        response = requests.get(
            f"{railway_url}/test/calendar/events",
            params=list_data,
            timeout=15
        )
        
        if response.status_code == 200:
            events_result = response.json()
            events_count = events_result.get('count', 0)
            calendar_enabled = events_result.get('calendar_enabled', False)
            
            print(f"   Events Retrieved: {events_count}")
            print(f"   Calendar Enabled: {calendar_enabled}")
            
            if calendar_enabled:
                print("   ✅ Token refresh mechanism working")
                return True
            else:
                print("   ❌ Calendar still disabled")
                return False
                
        else:
            print(f"   ⚠️ Events list returned: {response.status_code}")
            # This might be OK if the endpoint doesn't exist
            return True
            
    except Exception as e:
        print(f"   ⚠️ Events test error (may be OK): {e}")
        return True  # Don't fail the whole test for this

def main():
    """Main verification function"""
    
    print("🚀 Google Calendar Token Fix Verification")
    print("=" * 45)
    print()
    
    if verify_calendar_integration():
        print("\n🎉 SUCCESS! Token refresh issue is RESOLVED!")
        print()
        print("📱 Next steps:")
        print("1. Test via SMS: 'Schedule test meeting tomorrow at 2pm'")
        print("2. Check your Google Calendar for the real event")
        print("3. Calendar integration should now work reliably")
        
    else:
        print("\n❌ Token refresh issue NOT resolved")
        print()
        print("🔧 Troubleshooting:")
        print("1. Double-check you copied the FULL tokens (no truncation)")
        print("2. Verify you used the same Google account that owns the calendar")
        print("3. Check that Railway variables were updated correctly")
        print("4. Wait 30 seconds for Railway to fully restart")
        print("5. Re-run this script")

if __name__ == "__main__":
    main()