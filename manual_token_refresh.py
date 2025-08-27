#!/usr/bin/env python3
"""
Manual Google Calendar Token Refresh - Alternative to OAuth Playground
This script helps you refresh tokens without using OAuth Playground
"""

import urllib.parse
import requests
import json
import webbrowser

def manual_oauth_flow():
    """Manual OAuth flow to get new tokens without OAuth Playground"""
    
    print("🔧 Manual Google Calendar Token Refresh")
    print("=" * 42)
    print()
    print("This method bypasses the OAuth Playground redirect_uri_mismatch issue")
    print()
    
    # Your OAuth credentials - REPLACE WITH YOUR ACTUAL VALUES
    client_id = "YOUR_CLIENT_ID_FROM_RAILWAY_VARIABLES"
    client_secret = "YOUR_CLIENT_SECRET_FROM_RAILWAY_VARIABLES"
    
    # Step 1: Create authorization URL
    print("Step 1: Creating authorization URL...")
    
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',  # For desktop apps
        'scope': 'https://www.googleapis.com/auth/calendar',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(auth_params)
    
    print(f"✅ Authorization URL created")
    print()
    print("Step 2: Authorize in your browser")
    print("-" * 35)
    print("1. Click this URL or copy it to your browser:")
    print(f"   {auth_url}")
    print()
    print("2. Sign in with your Google account (the calendar owner)")
    print("3. Click 'Allow' to grant calendar permissions")
    print("4. You'll see a page with an authorization code")
    print("5. Copy the authorization code and paste it below")
    print()
    
    # Try to open browser automatically
    try:
        webbrowser.open(auth_url)
        print("✅ Browser opened automatically")
    except:
        print("⚠️ Could not open browser automatically - use the URL above")
    
    print()
    auth_code = input("Enter the authorization code: ").strip()
    
    if not auth_code:
        print("❌ No authorization code provided")
        return False
    
    # Step 3: Exchange code for tokens
    print("\nStep 3: Exchanging code for tokens...")
    
    token_data = {
        'code': auth_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post(
            'https://oauth2.googleapis.com/token',
            data=token_data,
            timeout=10
        )
        
        if response.status_code == 200:
            tokens = response.json()
            
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            expires_in = tokens.get('expires_in', 3600)
            
            print(f"✅ Tokens received successfully!")
            print(f"   Access token: {access_token[:20]}...")
            print(f"   Refresh token: {refresh_token[:20]}...")
            print(f"   Expires in: {expires_in} seconds")
            
            # Test the new tokens
            if test_tokens(access_token):
                print("\n✅ Token validation successful!")
                print_railway_instructions(access_token, refresh_token)
                return True
            else:
                print("\n❌ Token validation failed")
                return False
                
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            error_data = response.json() if response.content else {}
            print(f"   Error: {error_data}")
            
            if response.status_code == 400:
                error_type = error_data.get('error', '')
                if 'invalid_grant' in error_type:
                    print("\n💡 SOLUTION: The authorization code may have expired")
                    print("   Authorization codes expire in 10 minutes")
                    print("   Please try again and enter the code quickly")
                elif 'redirect_uri_mismatch' in error_type:
                    print("\n💡 SOLUTION: Redirect URI issue")
                    print("   This shouldn't happen with 'urn:ietf:wg:oauth:2.0:oob'")
                    print("   Your OAuth client may need different configuration")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during token exchange: {e}")
        return False

def test_tokens(access_token):
    """Test the new access token"""
    
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

def print_railway_instructions(access_token, refresh_token):
    """Print instructions for updating Railway"""
    
    print("\n" + "="*50)
    print("🚀 UPDATE RAILWAY ENVIRONMENT VARIABLES")
    print("="*50)
    print()
    print("1. Go to Railway Dashboard: https://railway.app")
    print("2. Open your 'smart-meeting-orchestrator' project")
    print("3. Click 'Variables' tab")
    print("4. Update these variables:")
    print()
    print("   GOOGLE_CALENDAR_ACCESS_TOKEN")
    print(f"   Value: {access_token}")
    print()
    print("   GOOGLE_CALENDAR_REFRESH_TOKEN")
    print(f"   Value: {refresh_token}")
    print()
    print("5. Save the changes")
    print("6. Railway will restart automatically")
    print()
    print("🧪 After Railway restarts, test with:")
    print("   python3 verify_token_fix.py")

def main():
    """Main function"""
    
    print("🔧 Google Calendar Token Refresh (OAuth Playground Alternative)")
    print("=" * 65)
    print()
    print("This script helps you get new Google Calendar tokens without")
    print("using OAuth Playground, avoiding the redirect_uri_mismatch error.")
    print()
    
    success = manual_oauth_flow()
    
    if success:
        print("\n🎉 SUCCESS! New tokens generated!")
        print("Follow the Railway instructions above to complete the setup.")
    else:
        print("\n❌ Token generation failed")
        print("\n🔧 Alternative solutions:")
        print("1. Add OAuth Playground redirect URI to your Google Cloud Console")
        print("2. Create a new OAuth2 client with proper redirect URIs")
        print("3. Use the service account method instead")

if __name__ == "__main__":
    main()