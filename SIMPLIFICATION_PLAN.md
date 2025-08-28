# SMS → LLM → MCP Google Calendar Simplification Plan

## 🎯 OBJECTIVE
Create a clean SMS frontend for MCP Google Calendar tools with LLM intelligence.

**Flow:** SMS Text → LLM Analysis → MCP Tool Selection → Google Calendar Action → SMS Response

## 📋 CURRENT STATE ANALYSIS

### What's Working ✅
- SMS webhook handling (`/webhook/sms`)
- LLM integration with Claude API
- MCP tool definitions for 8 Google Calendar functions
- Database models (Team, TeamMember, Conversation)
- Basic conversation context

### What's Complex/Broken ❌
- Multiple command processors (3+ different implementations)
- Fallback chains and compatibility layers
- Duplicate calendar client implementations
- Complex conversation state management
- Overly complex architecture with too many layers

## 🏗️ SIMPLIFIED ARCHITECTURE

```
SMS → FastAPI Webhook → SimpleSMSOrchestrator → LLM+MCP → Response
```

### Core Components (KEEP ONLY THESE)
1. **SMS Webhook Handler** - Entry point for SMS messages
2. **SimpleSMSOrchestrator** - Single class handling SMS → LLM → MCP flow
3. **MCP Google Calendar Client** - Direct connection to your 8 MCP tools
4. **LLM Tool Mapper** - Claude decides which MCP tool to call
5. **Response Generator** - Creates user-friendly SMS responses

## 🛠️ 8 MCP TOOL USE CASES

### 1. `google_calendar_create_event`
**SMS:** "Schedule family dinner tomorrow at 7pm"
**LLM:** Extracts title, time, attendees → Calls create_event
**Response:** "✅ Family dinner scheduled for Aug 29 at 7pm"

### 2. `google_calendar_list_events` 
**SMS:** "What meetings do I have today?"
**LLM:** Gets current date → Calls list_events
**Response:** "📅 Today: 9am Team standup, 3pm Client call"

### 3. `google_calendar_search_events`
**SMS:** "Find my meeting with Rick"
**LLM:** Extracts search term → Calls search_events
**Response:** "🔍 Found: Rick - Project Review, Aug 30 at 2pm"

### 4. `google_calendar_update_event`
**SMS:** "Move my 3pm meeting to 4pm"
**LLM:** Finds event → Calls update_event with new time
**Response:** "✅ Moved Client call from 3pm to 4pm"

### 5. `google_calendar_delete_event`
**SMS:** "Cancel tomorrow's family meeting"
**LLM:** Searches for event → Calls delete_event
**Response:** "✅ Cancelled Family meeting on Aug 29"

### 6. `google_calendar_get_event`
**SMS:** "Details about my morning meeting"
**LLM:** Finds specific event → Calls get_event
**Response:** "📋 Team standup: 9-9:30am, Meet link: meet.google.com/xyz"

### 7. `google_calendar_freebusy`
**SMS:** "When am I free this afternoon?"
**LLM:** Gets time range → Calls freebusy
**Response:** "⏰ Free slots: 1-2pm, 4:30-6pm"

### 8. `google_calendar_list_calendars`
**SMS:** "What calendars do I have?"
**LLM:** Calls list_calendars
**Response:** "📅 Calendars: Personal, Work, Family Events"

## 🗂️ FILES TO KEEP

### Core System
- `main.py` - FastAPI app with SMS webhook
- `simple_sms_orchestrator.py` - **NEW** - Single orchestration class
- `app/config.py` - Environment configuration
- `database/` - Keep models and connection

### MCP Integration (Existing)
- `mcp_integration/real_mcp_calendar_client.py` - Your 8 MCP tools
- Environment variable: `RAILWAY_MCP_ENDPOINT` (production only)

### SMS & Database
- `sms_coordinator/surge_client.py` - SMS sending
- `database/models.py` - Team, TeamMember, Conversation

## 🗑️ FILES TO REMOVE/ARCHIVE

### Multiple Command Processors
- `llm_integration/enhanced_command_processor.py` (2000+ lines!)
- `mcp_integration/mcp_command_processor.py` (700+ lines)
- `sms_coordinator/command_processor.py`
- `app/application/command_processor.py`

### Duplicate Calendar Clients
- `google_integrations/direct_google_calendar.py`
- `google_integrations/calendar_client.py`
- `adapters/calendar/mcp_calendar_provider.py`

### Legacy/Test Files
- All `main_*.py` variations (12+ files!)
- `supporting_modules*.py`
- Complex service initialization in `app/services.py`

## 🏗️ NEW SIMPLE IMPLEMENTATION

### 1. `simple_sms_orchestrator.py`
```python
class SimpleSMSOrchestrator:
    def __init__(self, mcp_calendar_client, sms_client):
        self.mcp_client = mcp_calendar_client
        self.sms_client = sms_client
        self.claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    async def process_sms(self, message: str, user_phone: str, user_name: str) -> str:
        # 1. LLM analyzes message and picks MCP tool
        tool_call = await self._llm_analyze(message)
        
        # 2. Execute MCP tool
        result = await self._execute_mcp_tool(tool_call)
        
        # 3. Generate user-friendly response
        return await self._generate_response(result, message)
```

### 2. Simplified `main.py`
```python
from simple_sms_orchestrator import SimpleSMSOrchestrator

# Initialize
orchestrator = SimpleSMSOrchestrator(mcp_client, sms_client)

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    # Parse SMS
    # Call orchestrator.process_sms()
    # Send response
```

## 🚀 IMPLEMENTATION STEPS

1. **Archive Legacy** - Move complex files to `/legacy` folder
2. **Create SimpleSMSOrchestrator** - Single class handling entire flow
3. **Test MCP Tools** - Ensure your 8 Google Calendar tools work
4. **Simplify main.py** - Clean FastAPI app with single webhook
5. **Test SMS Flow** - End-to-end testing with real SMS

## 🎯 SUCCESS CRITERIA

✅ SMS: "Schedule meeting tomorrow at 11am subject plan"
✅ LLM: Understands → Calls `google_calendar_create_event`
✅ MCP: Creates real Google Calendar event
✅ SMS Response: "✅ Meeting 'plan' scheduled for Aug 29 at 11am"

**No fallbacks, no complexity, no duplicate implementations - just SMS → LLM → MCP → Response!**
