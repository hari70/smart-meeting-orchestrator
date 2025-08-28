#!/usr/bin/env python3
"""
Test script for move meeting functionality
"""

import asyncio
import json
import logging
from simple_sms_orchestrator import SimpleSMSOrchestrator
from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
from sms_coordinator.surge_client import SurgeSMSClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_move_meeting_flow():
    """Test the move meeting functionality"""
    
    print("🧪 Testing Move Meeting Flow")
    print("=" * 50)
    
    # Initialize components
    mcp_client = RealMCPCalendarClient()
    sms_client = SurgeSMSClient(api_key="test", account_id="test")  # Mock for testing
    orchestrator = SimpleSMSOrchestrator(mcp_client, sms_client)
    
    # Test message
    test_message = 'Move the meeting "drop off" from tomorrow 10:30 am to 1 pm'
    test_user = "+12408029592"
    
    print(f"📱 Test SMS: '{test_message}'")
    print(f"👤 From: {test_user}")
    print()
    
    if not orchestrator.llm_enabled:
        print("⚠️ LLM not enabled - checking tool definitions...")
        
        # Show available tools
        print("🛠️ Available MCP Tools:")
        for i, tool in enumerate(orchestrator.mcp_tools, 1):
            print(f"  {i}. {tool['name']} - {tool['description']}")
        print()
        
        # Manually analyze what should happen
        print("🤔 Expected Analysis:")
        print("1. LLM should recognize this as a move/update request")
        print("2. First call: search_calendar_events(query='drop off')")
        print("3. Then call: update_calendar_event(event_id=found_id, start_time='2025-08-29T13:00:00')")
        print()
        
        print("❌ Can't test full flow without LLM - set ANTHROPIC_API_KEY")
        return
    
    try:
        # Test the full flow
        print("🚀 Testing full SMS processing flow...")
        response = await orchestrator.process_sms(test_message, test_user, None)
        
        print(f"✅ Response: {response}")
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run the test"""
    asyncio.run(test_move_meeting_flow())

if __name__ == "__main__":
    main()
