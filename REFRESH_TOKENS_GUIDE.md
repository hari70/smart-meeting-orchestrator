🚀 GOOGLE CALENDAR TOKEN REGENERATION GUIDE
================================================

Your refresh token has expired (401 Unauthorized). You need to generate fresh credentials.

STEP 1: Open OAuth 2.0 Playground
----------------------------------
Go to: https://developers.google.com/oauthplayground/

STEP 2: Configure OAuth Credentials
-----------------------------------
1. Click the ⚙️ gear icon (Settings) in the top right
2. Check "Use your own OAuth credentials"
3. Enter your credentials:
   - OAuth Client ID: [YOUR_CLIENT_ID_FROM_GOOGLE_CLOUD]
   - OAuth Client secret: [YOUR_CLIENT_SECRET_FROM_GOOGLE_CLOUD]
4. Click "Close"

STEP 3: Select API Scope
-------------------------
1. In the left panel, find "Google Calendar API v3"
2. Expand it and check this scope:
   ☑️ https://www.googleapis.com/auth/calendar
3. Click "Authorize APIs" button

STEP 4: Authorize with Google
-----------------------------
1. You'll be redirected to Google sign-in
2. **IMPORTANT**: Sign in with the SAME Google account that owns your calendar
3. Click "Allow" to grant calendar permissions
4. You'll be returned to OAuth Playground

STEP 5: Get Authorization Code
------------------------------
1. You should see "Authorization code" in Step 1 box
2. Click "Exchange authorization code for tokens"

STEP 6: Copy New Tokens
-----------------------
In Step 2, you'll see:
- Access token: (starts with ya29...)
- Refresh token: (starts with 1//...)

Copy BOTH tokens - you'll need them for Railway!

STEP 7: Update Railway Variables
--------------------------------
Go to Railway Dashboard → Your Project → Variables

Update these environment variables:
- GOOGLE_CALENDAR_ACCESS_TOKEN = [paste new access token]
- GOOGLE_CALENDAR_REFRESH_TOKEN = [paste new refresh token]

STEP 8: Test the Integration
----------------------------
After Railway restarts (should happen automatically):

Test endpoint:
curl -X POST "https://helpful-solace-production.up.railway.app/test/create-calendar-event" \
  -H "Content-Type: application/json" \
  -d '{"title": "Token Test", "hours_from_now": 2}'

Expected response should show:
- "google_calendar_working": true
- "integration_type": "real_google_api"

STEP 9: Test via SMS
--------------------
Send to your Surge SMS number:
"Schedule test meeting tomorrow at 2pm"

Should create a REAL Google Calendar event!

🚨 TROUBLESHOOTING:
==================

If you get "redirect_uri_mismatch":
- Go to Google Cloud Console → APIs & Services → Credentials
- Click your OAuth 2.0 Client ID
- Add this to "Authorized redirect URIs":
  https://developers.google.com/oauthplayground

If you get "access_denied":
- Make sure you're using the correct Google account
- Check that Google Calendar API is enabled in your project

If tokens still don't work:
- Double-check you copied the FULL tokens (no truncation)
- Verify the Google account has calendar access
- Try creating a test event manually in Google Calendar first