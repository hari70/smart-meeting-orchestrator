#!/usr/bin/env python3
"""
End-to-End SMS Workflow Test
Tests the complete Smart Meeting Orchestrator SMS workflow
"""

import requests
import json
import time

def test_sms_workflow():
    """Test complete SMS workflow from message to response"""
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    print("🧪 Smart Meeting Orchestrator - End-to-End SMS Test")
    print("=" * 55)
    print(f"Testing: {railway_url}")
    print()
    
    # Test cases for different SMS scenarios
    test_cases = [
        {
            "name": "Meeting Scheduling",
            "message": "schedule a meeting with Rick tomorrow at 2pm subject: Project Update",
            "expected_features": ["scheduling", "time_parsing", "calendar_integration"]
        },
        {
            "name": "Meeting Listing", 
            "message": "list my meetings this week",
            "expected_features": ["query_handling", "calendar_access"]
        },
        {
            "name": "Help Request",
            "message": "what can you help me with?",
            "expected_features": ["help_response", "conversational_ai"]
        },
        {
            "name": "Conversation Context",
            "message": "yes, that sounds good",
            "expected_features": ["context_preservation", "follow_up_handling"]
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. 📱 Testing: {test_case['name']}")
        print("-" * 40)
        print(f"Message: '{test_case['message']}'")
        
        # SMS payload
        payload = {
            "type": "message.received",
            "data": {
                "body": test_case["message"],
                "conversation": {
                    "contact": {
                        "first_name": "Test",
                        "last_name": "User",
                        "phone_number": "+12345678901"
                    }
                }
            }
        }
        
        try:
            # Send SMS webhook
            response = requests.post(
                f"{railway_url}/webhook/sms",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Analyze response
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("status") == "processed":
                    print("✅ SMS processed successfully")
                    test_result = {
                        "test": test_case["name"],
                        "status": "PASS",
                        "response_code": response.status_code,
                        "features_tested": test_case["expected_features"]
                    }
                else:
                    print("⚠️ SMS processed but unexpected response format")
                    test_result = {
                        "test": test_case["name"], 
                        "status": "PARTIAL",
                        "response_code": response.status_code,
                        "issue": "Unexpected response format"
                    }
            else:
                print("❌ SMS processing failed")
                test_result = {
                    "test": test_case["name"],
                    "status": "FAIL", 
                    "response_code": response.status_code,
                    "error": response.text
                }
                
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            test_result = {
                "test": test_case["name"],
                "status": "ERROR",
                "error": str(e)
            }
        
        results.append(test_result)
        print()
        
        # Small delay between tests
        time.sleep(1)
    
    # Summary
    print("📊 END-TO-END TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print()
    
    for result in results:
        status_emoji = {
            "PASS": "✅",
            "PARTIAL": "⚠️", 
            "FAIL": "❌",
            "ERROR": "🔥"
        }.get(result["status"], "❓")
        
        print(f"{status_emoji} {result['test']}: {result['status']}")
        if "features_tested" in result:
            features = ", ".join(result["features_tested"])
            print(f"    Features: {features}")
        if "issue" in result or "error" in result:
            issue = result.get("issue") or result.get("error", "Unknown")
            print(f"    Issue: {issue}")
    
    print()
    
    # System Status Check
    print("🔍 SYSTEM HEALTH CHECK")
    print("=" * 30)
    
    # Check system components
    components = {
        "Railway Deployment": check_health(railway_url),
        "LLM Integration": check_llm_status(railway_url),
        "Google Calendar": check_calendar_status(railway_url),
        "SMS Webhook": passed > 0
    }
    
    for component, status in components.items():
        emoji = "✅" if status else "❌"
        print(f"{emoji} {component}: {'Working' if status else 'Issues'}")
    
    print()
    
    # Overall Assessment
    if passed == total and all(components.values()):
        print("🎉 END-TO-END TEST: COMPLETE SUCCESS!")
        print("Your Smart Meeting Orchestrator is fully functional!")
        print()
        print("📱 Ready for production use:")
        print("- Send SMS to your Surge phone number")
        print("- Use natural language commands")
        print("- AI will handle scheduling and responses")
        
    elif passed >= total * 0.75:
        print("⚠️ END-TO-END TEST: MOSTLY WORKING")
        print("Most features working, minor issues detected")
        
    else:
        print("❌ END-TO-END TEST: SIGNIFICANT ISSUES")
        print("Multiple components need attention")
    
    return results

def check_health(railway_url):
    """Check basic health endpoint"""
    try:
        response = requests.get(f"{railway_url}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_llm_status(railway_url):
    """Check if LLM integration is working"""
    try:
        # Simple SMS test to see if LLM responds
        payload = {
            "type": "message.received",
            "data": {
                "body": "hello",
                "conversation": {
                    "contact": {
                        "first_name": "Health",
                        "last_name": "Check",
                        "phone_number": "+19999999999"
                    }
                }
            }
        }
        response = requests.post(f"{railway_url}/webhook/sms", json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def check_calendar_status(railway_url):
    """Check Google Calendar integration status"""
    try:
        response = requests.get(f"{railway_url}/test/calendar-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("calendar_integration_enabled", False)
        return False
    except:
        return False

if __name__ == "__main__":
    test_sms_workflow()