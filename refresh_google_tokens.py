#!/usr/bin/env python3
"""
Script to refresh Google Calendar tokens using OAuth credentials
"""

import requests
import json
import os

def refresh_google_calendar_token():
    """Refresh Google Calendar access token using refresh token"""
    
    print("🔄 Google Calendar Token Refresh")
    print("=" * 40)
    
    # Get current credentials from Railway (these are the ones that need to work)
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("1. Getting current credentials from Railway...")
    try:
        response = requests.get(f"{railway_url}/test/environment-check", timeout=10)
        if response.status_code == 200:
            env_data = response.json()
            env_vars = env_data.get('environment_status', {})
            
            # Extract the masked values - we need the full values
            client_id_masked = env_vars.get('GOOGLE_CALENDAR_CLIENT_ID', '')
            client_secret_masked = env_vars.get('GOOGLE_CALENDAR_CLIENT_SECRET', '')
            refresh_token_masked = env_vars.get('GOOGLE_CALENDAR_REFRESH_TOKEN', '')
            
            print(f"   Client ID: {client_id_masked}")
            print(f"   Client Secret: {client_secret_masked}")
            print(f"   Refresh Token: {refresh_token_masked}")
            
            if client_id_masked and client_secret_masked and refresh_token_masked:
                print("✅ All credentials found in Railway")
                
                # We need the FULL (unmasked) values for the refresh
                print("\n❗ IMPORTANT: The refresh needs your FULL (unmasked) credentials")
                print("Please provide them from your Railway dashboard:")
                print()
                
                client_id = input("Enter FULL Client ID (from Railway Variables tab): ").strip()
                client_secret = input("Enter FULL Client Secret (from Railway Variables tab): ").strip()
                refresh_token = input("Enter FULL Refresh Token (from Railway Variables tab): ").strip()
                
                return refresh_token_with_credentials(client_id, client_secret, refresh_token)
            else:
                print("❌ Missing credentials in Railway")
                return False
                
        else:
            print(f"❌ Failed to get credentials: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting credentials: {e}")
        return False

def refresh_token_with_credentials(client_id, client_secret, refresh_token):
    """Refresh the access token using OAuth credentials"""
    
    print("\n2. Refreshing access token...")
    
    # Google's token refresh endpoint
    token_url = "https://oauth2.googleapis.com/token"
    
    # Prepare refresh request
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            
            print(f"✅ New access token received!")
            print(f"   Token: {new_access_token[:20]}...")
            print(f"   Expires in: {expires_in} seconds ({expires_in//3600} hours)")
            
            # Test the new token
            if test_new_token(new_access_token):
                print("\n✅ Token validation successful!")
                print("\n📋 Next steps:")
                print("1. Go to Railway Dashboard → Your Project → Variables")
                print("2. Update GOOGLE_CALENDAR_ACCESS_TOKEN with this new value:")
                print(f"   {new_access_token}")
                print("3. Your application will restart automatically")
                print("4. Test with SMS: 'Schedule test meeting tomorrow at 2pm'")
                
                return True
            else:
                print("❌ New token validation failed")
                return False
                
        else:
            print(f"❌ Token refresh failed: {response.status_code}")
            error_data = response.json() if response.content else {}
            error_description = error_data.get('error_description', 'Unknown error')
            print(f"   Error: {error_description}")
            
            if response.status_code == 400:
                error_type = error_data.get('error', '')
                if error_type == 'invalid_grant':
                    print("\n🔧 SOLUTION: Your refresh token has expired")
                    print("You need to regenerate it using OAuth Playground:")
                    print("1. Go to: https://developers.google.com/oauthplayground/")
                    print("2. Click ⚙️ → Use your own OAuth credentials")
                    print(f"3. Enter Client ID: {client_id}")
                    print(f"4. Enter Client Secret: {client_secret}")
                    print("5. Select Google Calendar API v3 scope")
                    print("6. Authorize and get new refresh_token")
                    print("7. Update GOOGLE_CALENDAR_REFRESH_TOKEN in Railway")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during token refresh: {e}")
        return False

def test_new_token(access_token):
    """Test the new access token by making a simple API call"""
    
    print("\n3. Testing new token...")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        test_url = "https://www.googleapis.com/calendar/v3/calendars/primary"
        
        response = requests.get(test_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            calendar_data = response.json()
            calendar_summary = calendar_data.get('summary', 'Unknown')
            print(f"✅ Token test successful - Calendar: {calendar_summary}")
            return True
        else:
            print(f"❌ Token test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")
        return False

if __name__ == "__main__":
    refresh_google_calendar_token()