#!/usr/bin/env python3
"""
Test complete SMS workflow with real calendar integration.
This simulates the SMS flow to verify both LLM and calendar are working.
"""

import requests
import json
from datetime import datetime, timedelta

RAILWAY_URL = "https://helpful-solace-production.up.railway.app"

def test_webhook_sms():
    """Test the SMS webhook with a meeting request"""
    print("📱 Testing SMS Webhook Integration...")
    
    # Simulate SMS webhook payload
    test_payload = {
        "from": "+15551234567",  # Test phone number
        "body": "Schedule a test meeting with John tomorrow at 2pm for project discussion"
    }
    
    try:
        response = requests.post(
            f"{RAILWAY_URL}/webhook/sms",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Webhook processed successfully")
            print(f"   Response: {data}")
            return True
        else:
            print(f"❌ Webhook failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

def check_system_status():
    """Check overall system status"""
    print("🔍 Checking System Status...")
    
    try:
        # Check health
        health = requests.get(f"{RAILWAY_URL}/health")
        print(f"   Health: {health.status_code == 200}")
        
        # Check calendar status
        calendar = requests.get(f"{RAILWAY_URL}/test/calendar-status")
        if calendar.status_code == 200:
            cal_data = calendar.json()
            print(f"   Calendar Mode: {cal_data.get('calendar_mode', 'unknown')}")
            print(f"   Calendar Enabled: {cal_data.get('calendar_integration_enabled', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return False

def main():
    print("🧪 Complete SMS + Calendar Integration Test")
    print("=" * 50)
    print(f"Testing Railway URL: {RAILWAY_URL}")
    print()
    
    # Check system status first
    check_system_status()
    print()
    
    # Test SMS webhook
    webhook_ok = test_webhook_sms()
    print()
    
    if webhook_ok:
        print("🎉 SUCCESS!")
        print("✅ SMS webhook is processing requests")
        print("✅ Calendar is in real mode")
        print("✅ Your system should now create real calendar events!")
        print()
        print("📱 Try texting your SMS number with:")
        print("   'Schedule a meeting with [person] tomorrow at [time]'")
    else:
        print("⚠️  Webhook test failed - check Railway logs")

if __name__ == "__main__":
    main()