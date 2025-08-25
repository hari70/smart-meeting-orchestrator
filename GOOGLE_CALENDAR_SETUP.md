# Google Calendar API Setup Guide
Complete guide to enable real Google Calendar integration for Smart Meeting Orchestrator

## 🎯 Overview
This guide will help you set up Google Calendar API credentials so your SMS bot can create real calendar events instead of mock ones.

## 🚀 Quick Setup (Recommended)

### Option A: OAuth Playground (Fast, 1-hour access)

1. **Enable Google Calendar API**
   - Go to: https://console.cloud.google.com/
   - Create new project or select existing one
   - Go to "APIs & Services" → "Library"
   - Search "Google Calendar API" → Click "Enable"

2. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: "Web application"
   - Name: "Smart Meeting Orchestrator"
   - Authorized redirect URIs: `https://developers.google.com/oauthplayground`
   - Click "Create" → Copy Client ID and Client Secret

3. **Get Access Token**
   - Go to: https://developers.google.com/oauthplayground/
   - Click ⚙️ (settings) → Check "Use your own OAuth credentials"
   - Enter your Client ID and Client Secret from step 2
   - In left panel, select "Google Calendar API v3"
   - Check: `https://www.googleapis.com/auth/calendar`
   - Click "Authorize APIs" → Sign in with Google → Authorize
   - Click "Exchange authorization code for tokens"
   - Copy the `access_token` (starts with `ya29.`)

4. **Add to Railway**
   - Go to Railway Dashboard → Your Project → Variables
   - Add: `GOOGLE_CALENDAR_ACCESS_TOKEN=ya29.a0AcM612...`
   - Save (Railway will auto-redeploy)

✅ **Done! Calendar integration working for 1 hour**

### Option B: Refresh Token (Permanent Solution)

Follow steps 1-3 from Option A, then:

4. **Get Refresh Token**
   - In OAuth Playground, copy the `refresh_token` (starts with `1//`)

5. **Add to Railway**
   ```
   GOOGLE_CALENDAR_REFRESH_TOKEN=1//0GWy...
   GOOGLE_CALENDAR_CLIENT_ID=1088320123456-abc123def456.apps.googleusercontent.com
   GOOGLE_CALENDAR_CLIENT_SECRET=GOCSPX-...
   ```

✅ **Permanent solution - tokens auto-refresh**

## 🧪 Test Your Setup

After adding environment variables:

1. **Test Calendar Creation Endpoint**
   ```bash
   curl -X POST https://helpful-solace-production.up.railway.app/test/create-calendar-event \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Calendar Event",
       "hours_from_now": 2,
       "duration_minutes": 30
     }'
   ```

2. **Test via SMS**
   - Send SMS to your Surge phone number:
   - "Schedule a test meeting tomorrow at 2pm"
   - Should create real Google Calendar event!

## 🔧 Advanced Setup (Production)

### Option C: Service Account

1. **Create Service Account**
   - Google Cloud Console → "IAM & Admin" → "Service Accounts"
   - Click "Create Service Account"
   - Name: "smart-meeting-calendar"
   - Click "Create and Continue" → Skip optional steps

2. **Generate Key**
   - Click on service account → "Keys" tab
   - "Add Key" → "Create New Key" → JSON → Download

3. **Share Calendar**
   - Open Google Calendar → Settings → Share with specific people
   - Add service account email (ends with `.iam.gserviceaccount.com`)
   - Give "Make changes to events" permission

4. **Extract Credentials from JSON**
   ```json
   {
     "private_key": "-----BEGIN PRIVATE KEY-----\n...",
     "client_email": "smart-meeting-calendar@project.iam.gserviceaccount.com"
   }
   ```

5. **Add to Railway**
   ```
   GOOGLE_CALENDAR_SERVICE_ACCOUNT_EMAIL=smart-meeting-calendar@project.iam.gserviceaccount.com
   GOOGLE_CALENDAR_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...
   ```

## 🚨 Troubleshooting

### Common Issues:

**"Invalid credentials"**
- Check Client ID/Secret are correct
- Verify redirect URI matches exactly
- Ensure Google Calendar API is enabled

**"Access denied"** 
- Make sure you selected correct Google account
- Check calendar sharing permissions
- Verify OAuth scope includes calendar access

**"Token expired"**
- Access tokens expire in 1 hour (use refresh token)
- Refresh tokens last indefinitely
- Service account keys don't expire

**"Calendar not found"**
- Default calendar ID is "primary"
- For specific calendar, get ID from Calendar settings

## 📱 SMS Commands That Will Work

Once setup is complete, these SMS commands will create real calendar events:

- "Schedule dinner with family tomorrow at 7pm"
- "Book meeting with John next Tuesday at 2pm"
- "Create event: Doctor appointment Friday at 10am"
- "Schedule lunch meeting tomorrow at noon"

## 🎉 Success Indicators

You'll know it's working when:
- SMS responses mention real calendar links
- Events appear in your Google Calendar
- Test endpoint returns `"source": "real_google_api"`
- No more "mock" in event responses

## 💡 Quick Start Recommendation

**For immediate testing**: Use Option A (1-hour access token)
**For production use**: Use Option B (refresh token)
**For enterprise**: Use Option C (service account)

Need help? Check Railway logs or test the endpoints directly!