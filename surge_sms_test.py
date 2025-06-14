# surge_sms_test.py - Test your Surge SMS API setup
import os
import requests
import json
from datetime import datetime

class SurgeSMSTest:
    def __init__(self, api_key, account_id):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.surge.app"
        
    def send_test_message(self, to_number, message, first_name="Test", last_name="User"):
        """Send a test SMS message using Surge API format"""
        url = f"{self.base_url}/accounts/{self.account_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "body": message,
            "conversation": {
                "contact": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone_number": to_number
                }
            }
        }
        
        try:
            print(f"🚀 Sending SMS to {to_number}...")
            print(f"📱 Message: {message}")
            print(f"🏢 Account ID: {self.account_id}")
            print(f"🔗 URL: {url}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            print(f"📋 Response: {response.text}")
            
            if response.status_code in [200, 201]:
                response_data = response.json() if response.text else {}
                print("✅ SMS API call successful!")
                print(f"📊 Status: {response.status_code} ({'Created' if response.status_code == 201 else 'OK'})")
                
                # Check if there are any warnings or details in the response
                if response_data:
                    print(f"📋 Response details: {json.dumps(response_data, indent=2)}")
                
                # Different messages for demo vs real numbers
                if "+1801555" in to_number:
                    print("📞 Demo number used - no actual SMS sent")
                else:
                    print("📱 SMS should be delivered to your phone shortly!")
                    print("⏰ If you don't receive it in 2-3 minutes, check:")
                    print("   • Your phone number is verified with Surge")
                    print("   • You've opted in to receive messages")
                    print("   • Check spam/blocked messages")
                
                return True
            else:
                print("❌ Failed to send SMS")
                if response.status_code == 401:
                    print("   🔑 Check your API key is correct")
                elif response.status_code == 404:
                    print("   🏢 Check your account ID is correct")
                elif response.status_code == 400:
                    print("   📝 Check your message format and phone number")
                elif response.status_code == 403:
                    print("   🚫 Phone number might need verification or opt-in")
                else:
                    print(f"   🔍 Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"💥 Error sending SMS: {str(e)}")
            return False

def main():
    print("🧪 Surge SMS API Test Script - CORRECTED VERSION")
    print("=" * 50)
    
    # Get credentials from environment or user input
    api_key = os.getenv("SURGE_SMS_API_KEY")
    account_id = os.getenv("SURGE_ACCOUNT_ID")
    
    if not api_key:
        api_key = input("Enter your Surge SMS API Key (sk_live_...): ").strip()
    
    if not account_id:
        print("\n🔍 To find your Account ID:")
        print("1. Go to https://hq.surge.app/")
        print("2. Login to your dashboard")
        print("3. Look for Account ID (format: acct_...)")
        account_id = input("\nEnter your Surge Account ID (acct_...): ").strip()
    
    if not account_id.startswith('acct_'):
        print("⚠️  Account ID should start with 'acct_'. Please double-check.")
    
    # Initialize SMS client
    sms_client = SurgeSMSTest(api_key, account_id)
    
    # Skip account info check - go straight to message test
    print("\n📱 SMS Message Test")
    test_number = input("Enter your phone number to receive test SMS (format: +1234567890): ").strip()
    
    if not test_number:
        print("❌ Phone number required for SMS test")
        return
    
    # Validate phone number format
    if not test_number.startswith('+'):
        print("⚠️  Phone number should start with '+' and include country code")
        test_number = '+' + test_number.lstrip('+')
    
    test_message = f"🎉 Smart Meeting Orchestrator test from Surge SMS! Time: {datetime.now().strftime('%H:%M:%S')}"
    
    first_name = input("Enter your first name (for contact): ").strip() or "Test"
    last_name = input("Enter your last name (for contact): ").strip() or "User"
    
    success = sms_client.send_test_message(test_number, test_message, first_name, last_name)
    
    if success:
        print("\n✅ All tests passed! Your Surge SMS setup is working.")
        print("\n📋 Next steps:")
        print("1. Add these to your Railway environment variables:")
        print(f"   SURGE_SMS_API_KEY={api_key}")
        print(f"   SURGE_ACCOUNT_ID={account_id}")
        print("2. Deploy the SMS Coordination MCP")
        print("3. Set up webhook endpoint in Surge dashboard")
        print("\n📖 Webhook setup:")
        print("1. Go to https://hq.surge.app/webhooks")
        print("2. Add webhook URL: https://your-railway-app.up.railway.app/webhook/sms")
        print("3. Enable 'message received' events")
    else:
        print("\n❌ SMS test failed. Please check:")
        print("1. API key is correct (starts with sk_live_)")
        print("2. Account ID is correct (starts with acct_)")
        print("3. Phone number format includes country code (+1234567890)")
        print("4. Your Surge account has sufficient balance")
        print("5. Your account is properly verified with Surge")
        
        print("\n🔧 Common fixes:")
        print("- Double-check Account ID from https://hq.surge.app/")
        print("- Ensure you're using the live API key, not demo")
        print("- Verify your Surge account is fully set up and verified")

if __name__ == "__main__":
    main()

# Additional utility functions for development

def test_webhook_format():
    """Test what a Surge SMS webhook payload looks like"""
    sample_webhook = {
        "event": "message.received",
        "message": {
            "id": "msg_01jk2m3n4p5q6r7s8t9u0v1w2x",
            "body": "Family meeting about vacation this weekend",
            "direction": "inbound",
            "created_at": "2024-01-15T10:30:00Z",
            "conversation": {
                "id": "conv_01jk2m3n4p5q6r7s8t9u0v1w2x",
                "contact": {
                    "id": "contact_01jk2m3n4p5q6r7s8t9u0v1w2x",
                    "phone_number": "+1234567890",
                    "first_name": "John",
                    "last_name": "Smith"
                }
            }
        },
        "account": {
            "id": "acct_01jn0dw93aekpa64wvx8gc2h4f"
        }
    }
    
    print("\n📋 Sample Surge SMS Webhook Payload:")
    print(json.dumps(sample_webhook, indent=2))
    
    return sample_webhook

def validate_phone_number(phone):
    """Basic phone number validation"""
    import re
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Check if it starts with + and has 10-15 digits
    if re.match(r'^\+\d{10,15}$', cleaned):
        return cleaned
    else:
        print(f"❌ Invalid phone number format: {phone}")
        print("   Use format: +1234567890 (with country code)")
        return None

# Run additional tests
if __name__ == "__main__":
    main()
    
    print("\n" + "="*50)
    print("📋 Additional Information:")
    test_webhook_format()
    
    print("\n🔧 Phone Number Validation Test:")
    test_numbers = ["+1234567890", "123-456-7890", "(123) 456-7890", "+44 20 7946 0958"]
    
    for num in test_numbers:
        result = validate_phone_number(num)
        if result:
            print(f"✅ {num} → {result}")
        else:
            print(f"❌ {num} → Invalid")