#!/usr/bin/env python3
"""
Google Calendar Token Refresh Script
Forces refresh of Google Calendar tokens and restarts integration
"""

import requests
import json

def refresh_calendar_integration():
    """Force refresh of Google Calendar integration on Railway"""
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("🔄 Google Calendar Token Refresh & Integration Restart")
    print("=" * 55)
    
    # Step 1: Check current calendar status
    print("1. 📅 Checking Current Calendar Status")
    print("-" * 40)
    
    try:
        response = requests.get(f"{railway_url}/test/calendar-status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print(f"Current Mode: {status.get('calendar_mode', 'unknown')}")
            print(f"Integration Enabled: {status.get('calendar_integration_enabled', False)}")
            
            creds = status.get('credentials_status', {})
            print(f"Has Access Token: {creds.get('has_access_token', False)}")
            print(f"Has Refresh Token: {creds.get('has_refresh_token', False)}")
            print(f"Has OAuth Creds: {creds.get('has_oauth_credentials', False)}")
        else:
            print(f"❌ Failed to get calendar status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking calendar status: {e}")
    
    print()
    
    # Step 2: Test current calendar creation
    print("2. 🧪 Testing Current Calendar Creation")
    print("-" * 40)
    
    try:
        test_payload = {
            "title": "Token Refresh Test Event",
            "hours_from_now": 1,
            "duration_minutes": 30
        }
        
        response = requests.post(
            f"{railway_url}/test/create-calendar-event",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            integration_type = result.get('integration_type', 'unknown')
            working = result.get('google_calendar_working', False)
            
            print(f"Integration Type: {integration_type}")
            print(f"Calendar Working: {working}")
            
            if integration_type == "mock_mode":
                print("❌ Still in mock mode - token refresh needed")
                needs_refresh = True
            else:
                print("✅ Real calendar integration working!")
                needs_refresh = False
        else:
            print(f"❌ Calendar test failed: {response.status_code}")
            needs_refresh = True
    except Exception as e:
        print(f"❌ Error testing calendar: {e}")
        needs_refresh = True
    
    print()
    
    # Step 3: Check environment variables
    print("3. 🔧 Checking Environment Variables")
    print("-" * 40)
    
    try:
        response = requests.get(f"{railway_url}/test/environment-check", timeout=10)
        if response.status_code == 200:
            env_status = response.json()
            env_vars = env_status.get('environment_status', {})
            
            print("Google Calendar Environment Variables:")
            for var, status in env_vars.items():
                if 'GOOGLE_CALENDAR' in var:
                    print(f"  {var}: {status}")
            
            # Check if we have the minimum required credentials
            has_access_token = env_vars.get('GOOGLE_CALENDAR_ACCESS_TOKEN', 'NOT_SET') != 'NOT_SET'
            has_refresh_token = env_vars.get('GOOGLE_CALENDAR_REFRESH_TOKEN', 'NOT_SET') != 'NOT_SET'
            has_client_id = env_vars.get('GOOGLE_CALENDAR_CLIENT_ID', 'NOT_SET') != 'NOT_SET'
            has_client_secret = env_vars.get('GOOGLE_CALENDAR_CLIENT_SECRET', 'NOT_SET') != 'NOT_SET'
            
            if has_refresh_token and has_client_id and has_client_secret:
                print("✅ Refresh token setup available")
                refresh_method = "refresh_token"
            elif has_access_token:
                print("⚠️ Only access token available (will expire in 1 hour)")
                refresh_method = "access_token"
            else:
                print("❌ No Google Calendar credentials found")
                refresh_method = None
                
    except Exception as e:
        print(f"❌ Error checking environment: {e}")
        refresh_method = None
    
    print()
    
    # Step 4: Provide solutions
    print("4. 🛠️ Solutions")
    print("-" * 40)
    
    if needs_refresh:
        print("GOOGLE CALENDAR TOKEN REFRESH NEEDED:")
        print()
        
        if refresh_method == "refresh_token":
            print("✅ AUTOMATIC REFRESH POSSIBLE:")
            print("Your refresh token should work automatically.")
            print("Issue: Calendar client needs restart to pick up tokens.")
            print()
            print("SOLUTION: Force Railway restart")
            print("1. Go to Railway Dashboard")
            print("2. Navigate to your Smart Meeting Orchestrator project")  
            print("3. Go to 'Deployments' tab")
            print("4. Click 'Redeploy' button")
            print("5. Wait 2-3 minutes for restart")
            print("6. Test again")
            
        elif refresh_method == "access_token":
            print("⚠️ ACCESS TOKEN REFRESH NEEDED:")
            print("Your access token expires in 1 hour. For permanent solution:")
            print()
            print("QUICK FIX (1 hour):")
            print("1. Go to: https://developers.google.com/oauthplayground/")
            print("2. Use your existing OAuth credentials")
            print("3. Get new access_token")
            print("4. Update GOOGLE_CALENDAR_ACCESS_TOKEN in Railway")
            print("5. Redeploy")
            print()
            print("PERMANENT FIX:")
            print("Follow GOOGLE_CALENDAR_SETUP.md for refresh token setup")
            
        else:
            print("❌ NO CREDENTIALS FOUND:")
            print("You need to set up Google Calendar API credentials.")
            print("Follow the complete setup guide in GOOGLE_CALENDAR_SETUP.md")
    else:
        print("🎉 Google Calendar integration is working correctly!")
    
    print()
    print("📋 NEXT STEPS:")
    print("1. Force restart Railway (if refresh token available)")
    print("2. Or refresh access token (if only access token)")  
    print("3. Or complete credentials setup (if none found)")
    print("4. Test with: curl -X POST [railway-url]/test/create-calendar-event")

if __name__ == "__main__":
    refresh_calendar_integration()