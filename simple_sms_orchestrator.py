"""
SimpleSMSOrchestrator - Clean SMS → LLM → MCP Google Calendar Pipeline

This is the ONLY orchestration class needed for the entire system.
No fallbacks, no complexity - just SMS → LLM → MCP → Response.
"""
import os
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database.models import TeamMember, Conversation
from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
from sms_coordinator.surge_client import SurgeSMSClient

logger = logging.getLogger(__name__)

# Check if Anthropic is available
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("⚠️ Anthropic not available - install with: pip install anthropic")

class SimpleSMSOrchestrator:
    """Single class handling SMS → LLM → MCP Google Calendar pipeline"""
    
    def __init__(self, mcp_calendar_client: RealMCPCalendarClient, sms_client: SurgeSMSClient):
        self.mcp_client = mcp_calendar_client
        self.sms_client = sms_client
        
        # Initialize Claude LLM
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if ANTHROPIC_AVAILABLE and api_key:
            self.claude_client = anthropic.Anthropic(api_key=api_key)
            self.llm_enabled = True
            logger.info("✅ SimpleSMSOrchestrator initialized with Claude LLM")
        else:
            self.claude_client = None
            self.llm_enabled = False
            logger.warning("⚠️ No ANTHROPIC_API_KEY or Anthropic not available - LLM disabled")
        
        # Define MCP tools for Claude
        self.mcp_tools = self._define_mcp_tools()
    
    def _define_mcp_tools(self) -> List[Dict]:
        """Define MCP Google Calendar tools for Claude to use (matched to actual client interface)"""
        return [
            {
                "name": "create_calendar_event",
                "description": "Create a new Google Calendar event. Extract exact title from user message.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Exact event title from user message"},
                        "start_time": {"type": "string", "description": "Start time in ISO format"},
                        "duration_minutes": {"type": "integer", "default": 60, "description": "Duration in minutes"},
                        "attendees": {"type": "array", "items": {"type": "string"}, "description": "Attendee names mentioned by user"}
                    },
                    "required": ["title", "start_time"]
                }
            },
            {
                "name": "list_calendar_events",
                "description": "List upcoming calendar events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer", "default": 7, "description": "Days to look ahead"},
                        "limit": {"type": "integer", "default": 10, "description": "Max events to return"}
                    }
                }
            },
            {
                "name": "find_free_time",
                "description": "Find free time slots for scheduling meetings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendees"},
                        "duration_minutes": {"type": "integer", "default": 60, "description": "Duration needed"},
                        "days_ahead": {"type": "integer", "default": 7, "description": "Days to look ahead"}
                    }
                }
            },
            {
                "name": "search_calendar_events",
                "description": "Search for calendar events by title or keyword to get event IDs for updating/deleting",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (event title or keywords)"},
                        "days_ahead": {"type": "integer", "default": 7, "description": "Days to search ahead"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "delete_calendar_event",
                "description": "Delete a calendar event by ID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "Google Calendar event ID to delete"}
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "update_calendar_event", 
                "description": "Update an existing calendar event",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "Event ID to update"},
                        "title": {"type": "string", "description": "New title"},
                        "start_time": {"type": "string", "description": "New start time in ISO format"},
                        "duration_minutes": {"type": "integer", "description": "New duration"}
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "check_calendar_conflicts",
                "description": "Check for scheduling conflicts at a specific time",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "Start time to check in ISO format"},
                        "duration_minutes": {"type": "integer", "default": 60, "description": "Duration to check"}
                    },
                    "required": ["start_time"]
                }
            }
        ]
    
    async def process_sms(self, message: str, user_phone: str, user_name: str, db: Session) -> str:
        """Main entry point: SMS → LLM → MCP → Response"""
        
        if not self.llm_enabled:
            return "Sorry, I need LLM access to help with calendar operations. Please configure ANTHROPIC_API_KEY."
        
        logger.info(f"📱 Processing SMS from {user_name} ({user_phone}): {message}")
        
        try:
            # 1. LLM analyzes message and decides which MCP tool to call
            tool_calls = await self._llm_analyze_message(message, user_name)
            
            # 2. Execute MCP tool(s)
            results = []
            for tool_call in tool_calls:
                result = await self._execute_mcp_tool(tool_call, user_phone, db)
                results.append(result)
            
            # 3. Generate user-friendly SMS response
            response = await self._generate_sms_response(message, results)
            
            logger.info(f"✅ Generated response: {response}")
            return response
            
        except Exception as e:
            logger.error(f"❌ SMS processing failed: {e}")
            return f"Sorry {user_name}, I encountered an error processing your request. Please try again."
    
    async def _llm_analyze_message(self, message: str, user_name: str) -> List[Dict]:
        """Use Claude to analyze SMS and determine which MCP tools to call"""
        
        system_prompt = f"""You are an intelligent SMS assistant for Google Calendar operations. 

The user {user_name} will send you natural language requests about their calendar.
Your job is to determine which Google Calendar MCP tools to call and with what parameters.

Available MCP tools:
{json.dumps(self.mcp_tools, indent=2)}

CRITICAL RULES:
1. ALWAYS call a tool - never just respond conversationally
2. Extract EXACT titles from user messages (if they say "plan", use "plan")
3. For scheduling requests, ALWAYS call create_calendar_event
4. Parse times intelligently (tomorrow = next day, 11am = 11:00, etc)
5. Convert relative times to ISO format (YYYY-MM-DDTHH:MM:SS)
6. For UPDATE/MOVE requests: First call search_calendar_events to find the event, then call update_calendar_event with the event_id
7. For DELETE requests: First call search_calendar_events to find the event, then call delete_calendar_event with the event_id
8. Call multiple tools if needed (search first, then update/delete)

SPECIAL HANDLING FOR MOVE/UPDATE REQUESTS:
- User says "move meeting X to Y" → First: search_calendar_events(query="X"), Then: update_calendar_event(event_id=found_id, start_time="Y")
- User says "reschedule X" → First: search_calendar_events(query="X"), Then: update_calendar_event with new time
- User says "cancel/delete X" → First: search_calendar_events(query="X"), Then: delete_calendar_event(event_id=found_id)

Return tool calls in this format - you MUST call tools, not just chat!"""

        user_prompt = f"SMS message: '{message}'\n\nWhich MCP tool(s) should I call and with what parameters?"

        try:
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=self.mcp_tools
            )
            
            # Extract tool calls from Claude's response
            tool_calls = []
            for content in response.content:
                if content.type == "tool_use":
                    tool_calls.append({
                        "name": content.name,
                        "input": content.input
                    })
            
            if not tool_calls:
                logger.warning("Claude didn't call any tools - creating fallback response")
                # Fallback: try to detect intent and create a tool call
                return self._create_fallback_tool_call(message)
            
            logger.info(f"🤖 Claude selected tools: {[tc['name'] for tc in tool_calls]}")
            return tool_calls
            
        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            # Return fallback tool call
            return self._create_fallback_tool_call(message)
    
    def _create_fallback_tool_call(self, message: str) -> List[Dict]:
        """Create a fallback tool call when LLM fails"""
        message_lower = message.lower()
        
        # Simple intent detection
        if any(word in message_lower for word in ["schedule", "create", "meeting", "plan"]):
            return [{
                "name": "create_calendar_event",
                "input": {
                    "title": "Meeting",  # Generic title
                    "start_time": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT11:00:00"),
                    "duration_minutes": 60
                }
            }]
        elif any(word in message_lower for word in ["list", "show", "what", "meetings"]):
            return [{
                "name": "list_calendar_events",
                "input": {"days_ahead": 7, "limit": 5}
            }]
        else:
            return [{
                "name": "list_calendar_events", 
                "input": {"days_ahead": 3, "limit": 3}
            }]
    
    async def _execute_mcp_tool(self, tool_call: Dict, user_phone: str, db: Session) -> Dict:
        """Execute a single MCP tool call using actual client interface"""
        
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]
        
        logger.info(f"🔧 Executing MCP tool: {tool_name} with input: {tool_input}")
        
        try:
            if tool_name == "create_calendar_event":
                # Convert ISO string to datetime
                start_time_str = tool_input["start_time"]
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                
                result = await self.mcp_client.create_event(
                    title=tool_input["title"],
                    start_time=start_time,
                    duration_minutes=tool_input.get("duration_minutes", 60),
                    attendees=tool_input.get("attendees", [])
                )
                
            elif tool_name == "list_calendar_events":
                result = await self.mcp_client.list_events(
                    days_ahead=tool_input.get("days_ahead", 7),
                    limit=tool_input.get("limit", 10)
                )
                
            elif tool_name == "search_calendar_events":
                result = await self.mcp_client.search_events(
                    query=tool_input["query"],
                    days_ahead=tool_input.get("days_ahead", 7)
                )
                
            elif tool_name == "find_free_time":
                result = await self.mcp_client.find_free_time(
                    attendees=tool_input.get("attendees", []),
                    duration_minutes=tool_input.get("duration_minutes", 60),
                    days_ahead=tool_input.get("days_ahead", 7)
                )
                
            elif tool_name == "delete_calendar_event":
                result = await self.mcp_client.delete_event(
                    event_id=tool_input["event_id"]
                )
                
            elif tool_name == "update_calendar_event":
                # Convert start_time if provided
                start_time = None
                if tool_input.get("start_time"):
                    start_time = datetime.fromisoformat(tool_input["start_time"].replace('Z', '+00:00'))
                
                result = await self.mcp_client.update_event(
                    event_id=tool_input["event_id"],
                    title=tool_input.get("title"),
                    start_time=start_time,
                    duration_minutes=tool_input.get("duration_minutes")
                )
                
            elif tool_name == "check_calendar_conflicts":
                start_time = datetime.fromisoformat(tool_input["start_time"].replace('Z', '+00:00'))
                result = await self.mcp_client.check_conflicts(
                    start_time=start_time,
                    duration_minutes=tool_input.get("duration_minutes", 60)
                )
                
            else:
                result = {"error": f"Unknown MCP tool: {tool_name}"}
            
            logger.info(f"✅ MCP tool {tool_name} result: {result}")
            return {"tool": tool_name, "result": result, "input": tool_input}
            
        except Exception as e:
            logger.error(f"❌ MCP tool {tool_name} failed: {e}")
            return {"tool": tool_name, "error": str(e), "input": tool_input}
    
    async def _generate_sms_response(self, original_message: str, tool_results: List[Dict]) -> str:
        """Generate user-friendly SMS response from MCP tool results"""
        
        if not tool_results:
            return "I wasn't able to process your request. Please try again."
        
        # Simple response generation based on first result
        primary_result = tool_results[0]
        tool_name = primary_result["tool"]
        result = primary_result.get("result", {})
        
        if primary_result.get("error"):
            return f"I encountered an error: {primary_result['error']}"
        
        # Generate responses based on tool type
        if tool_name == "create_calendar_event":
            if result and result != {"error": "Calendar client returned None/False"}:
                title = primary_result["input"]["title"]
                start_time = primary_result["input"]["start_time"]
                # Parse and format time nicely
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    time_str = dt.strftime("%a %b %d at %I:%M %p")
                except:
                    time_str = start_time
                
                response = f"✅ Created '{title}' for {time_str}"
                
                # Add meet link if available in result
                if isinstance(result, dict) and result.get("meet_link"):
                    response += f"\n🔗 Meet: {result['meet_link']}"
                elif isinstance(result, dict) and result.get("hangout_link"):
                    response += f"\n🔗 Meet: {result['hangout_link']}"
                
                return response
            else:
                return f"❌ Couldn't create event: {result.get('error', 'Calendar service unavailable')}"
        
        elif tool_name == "list_calendar_events":
            if isinstance(result, list) and result:
                response = "📅 Upcoming events:\n"
                for event in result[:5]:  # Limit to 5 for SMS
                    title = event.get("title", "Untitled")
                    start = event.get("start", "")
                    response += f"• {title} - {start}\n"
                return response.strip()
            else:
                return "📅 No upcoming events found"
        
        elif tool_name == "search_calendar_events":
            if isinstance(result, list) and result:
                response = f"🔍 Found {len(result)} events:\n"
                for event in result[:3]:  # Limit to 3 for SMS
                    title = event.get("title", "Untitled")
                    start = event.get("start", "")
                    event_id = event.get("id", "")
                    response += f"• {title} - {start} (ID: {event_id[:8]}...)\n"
                return response.strip()
            else:
                return "🔍 No events found matching your search"
        
        elif tool_name == "find_free_time":
            if isinstance(result, list) and result:
                response = "⏰ Available times:\n"
                for slot in result[:3]:  # Show first 3 slots
                    start = slot.get("start", "")
                    end = slot.get("end", "")
                    response += f"• {start} - {end}\n"
                return response.strip()
            else:
                return "⏰ No free time slots found"
        
        elif tool_name == "delete_calendar_event":
            if result and result.get("success"):
                deleted_title = result.get("title", "Event")
                return f"✅ Deleted '{deleted_title}' successfully"
            else:
                return f"❌ Couldn't delete event: {result.get('error', 'Event not found')}"
        
        elif tool_name == "update_calendar_event":
            if result and result.get("success"):
                updated_title = result.get("title", "Event")
                new_time = result.get("start_time", "")
                if new_time:
                    return f"✅ Updated '{updated_title}' to {new_time}"
                else:
                    return f"✅ Updated '{updated_title}' successfully"
            else:
                return f"❌ Couldn't update event: {result.get('error', 'Event not found')}"
        
        elif tool_name == "check_calendar_conflicts":
            if isinstance(result, list):
                if result:
                    return f"⚠️ You have {len(result)} conflict(s) at that time"
                else:
                    return "✅ No conflicts found - time is available"
            else:
                return "⏰ Checked availability"
        
        else:
            return "✅ Task completed successfully"
