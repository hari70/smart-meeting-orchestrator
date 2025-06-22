# MCP_SETUP_GUIDE.md - How to connect your existing MCP Google Calendar tools

## 🎯 Problem: SMS Orchestrator Not Using Your Real MCP Tools

You have **8 Google Calendar MCP tools** exposed, but your SMS orchestrator is responding conversationally ("Hi Hari! I can meet Sunday...") instead of **actually calling your MCP tools** to create real calendar events.

## 🔧 Solution: Connect Your Existing MCP Tools

### Step 1: Enable Real MCP Integration

Add these environment variables in Railway:

```env
# Enable real MCP calendar integration
USE_REAL_MCP_CALENDAR=true

# Enable LLM intelligence (if not already set)
ANTHROPIC_API_KEY=sk-ant-your_claude_api_key_here

# Mark MCP tools as available (if needed)
MCP_CALENDAR_AVAILABLE=true
```

### Step 2: Configure MCP Tool Access

The system needs to know how to call your 8 MCP Google Calendar tools. Update the environment to include:

```env
# Your MCP tools configuration
MCP_SERVER_URL=http://localhost:your_mcp_port (if running MCP server)
# OR if tools are available globally:
MCP_CALENDAR_TOOLS_AVAILABLE=true
```

### Step 3: Deploy and Test

```bash
# Deploy the changes
git add .
git commit -m "🔗 Enable real MCP Google Calendar integration"
git push origin main
```

### Step 4: Test Real MCP Integration

**Check MCP Status:**
```bash
curl https://helpful-solace-production.up.railway.app/debug/mcp-status
```

**Expected Response:**
```json
{
  "mcp_integration": {
    "use_real_mcp_calendar": true,
    "calendar_client_type": "RealMCPCalendarClient",
    "command_processor_type": "MCPCommandProcessor",
    "mcp_calendar_available": true,
    "will_create_real_events": true
  }
}
```

**Test SMS Commands:**
```
Text: "Schedule family dinner tomorrow at 7pm"
Expected: Creates REAL Google Calendar event via your MCP tools
```

## 🔍 MCP Tool Integration Methods

Your SMS orchestrator will try to connect to your MCP tools using these methods:

### Method 1: Global MCP Functions (Claude Desktop)
```python
# If running in Claude Desktop with MCP tools:
result = await google_calendar_create_event(
    summary="Family Dinner",
    start={"dateTime": "2025-06-23T19:00:00"},
    end={"dateTime": "2025-06-23T20:00:00"}
)
```

### Method 2: MCP Server HTTP API
```python
# If running MCP tools as HTTP server:
async with aiohttp.ClientSession() as session:
    async with session.post(
        f"{MCP_SERVER_URL}/tools/google_calendar_create_event",
        json=event_data
    ) as response:
        result = await response.json()
```

### Method 3: Environment-Specific Access
```python
# If tools are available via __builtins__:
if hasattr(__builtins__, 'mcp_tools'):
    result = await __builtins__.mcp_tools.google_calendar_create_event(**params)
```

## 🎯 What Will Change

### Before (Current):
```
SMS: "Schedule family dinner tomorrow"
Response: "Hi Hari! I can meet tomorrow at 7pm. Let me know if that works! 👍"
Action: NO real calendar event created
```

### After (With MCP Integration):
```
SMS: "Schedule family dinner tomorrow"
Response: "✅ Meeting scheduled!
📅 Family Dinner
🕐 Sunday, June 23 at 7:00 PM
🔗 https://meet.google.com/abc-xyz
Action: REAL Google Calendar event created via your MCP tools
```

## 🧪 Testing Your 8 MCP Tools

Once configured, your SMS orchestrator will use these tools:

1. **google_calendar_create_event** - Creates real calendar events
2. **google_calendar_list_events** - Lists your actual meetings  
3. **google_calendar_get_event** - Gets specific event details
4. **google_calendar_update_event** - Updates existing events
5. **google_calendar_delete_event** - Deletes events
6. **google_calendar_freebusy** - Checks availability
7. **google_calendar_list_calendars** - Lists your calendars
8. **google_calendar_search_events** - Searches your events

## 🚀 Deploy Instructions

1. **Add environment variables** to Railway
2. **Deploy the enhanced system**
3. **Test with SMS**: "Schedule family meeting tomorrow at 7pm"
4. **Check your Google Calendar** - you should see a real event!

## 🔧 Troubleshooting

**If MCP tools still not working:**

1. **Check debug endpoint**: `/debug/mcp-status`
2. **Verify your MCP setup** - ensure tools are accessible
3. **Check Railway logs** for MCP connection errors
4. **Test individual tools** first before SMS integration

**Common Issues:**
- MCP tools not globally accessible → Set MCP_SERVER_URL
- Authentication issues → Check MCP tool credentials
- Network issues → Verify MCP server is running

## 🎉 Success Indicators

You'll know it's working when:

- ✅ `/debug/mcp-status` shows `"will_create_real_events": true`
- ✅ SMS responses include real meeting confirmations
- ✅ Events appear in your actual Google Calendar
- ✅ Railway logs show "🔗 Creating REAL calendar event via MCP"

Your SMS orchestrator will finally use your 8 MCP Google Calendar tools to create real events instead of just talking about them! 🚀