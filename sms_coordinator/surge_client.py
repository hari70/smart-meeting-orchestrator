import requests
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SurgeSMSClient:
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.surge.app"
        
        # Log initialization status
        logger.info(f"🔧 SurgeSMSClient initialized:")
        logger.info(f"   API Key: {'***' + (api_key[-4:] if api_key and len(api_key) > 4 else 'NOT_SET')}")
        logger.info(f"   Account ID: {account_id or 'NOT_SET'}")
        
    async def send_message(self, to_number: str, message: str, first_name: str = "User", last_name: str = "") -> bool:
        """Send SMS message via Surge API with detailed logging"""
        
        logger.info(f"📤 SMS SEND ATTEMPT:")
        logger.info(f"   To: {to_number}")
        logger.info(f"   Message: '{message[:100]}{'...' if len(message) > 100 else ''}'")
        logger.info(f"   Name: {first_name} {last_name}")
        
        # Check credentials
        if not self.api_key or not self.account_id:
            logger.error(f"❌ SMS SEND FAILED: Missing credentials")
            logger.error(f"   API Key: {bool(self.api_key)}")
            logger.error(f"   Account ID: {bool(self.account_id)}")
            return False
        
        url = f"{self.base_url}/accounts/{self.account_id}/messages"
        logger.info(f"🌐 SMS API URL: {url}")
        
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
        
        logger.info(f"📦 SMS Payload: {json.dumps(payload, indent=2)}")
        
        try:
            logger.info(f"🚀 Making HTTP POST request to Surge API...")
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            logger.info(f"📨 Surge API Response:")
            logger.info(f"   Status Code: {response.status_code}")
            logger.info(f"   Headers: {dict(response.headers)}")
            logger.info(f"   Body: {response.text}")
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ SMS sent successfully to {to_number}")
                return True
            else:
                logger.error(f"❌ SMS send failed with status {response.status_code}")
                logger.error(f"   Error response: {response.text}")
                
                # Try to parse error details
                try:
                    error_data = response.json()
                    logger.error(f"   Parsed error: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"   Could not parse error response as JSON")
                
                return False
                
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ SMS send timeout: {str(e)}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ SMS send connection error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ SMS send unexpected error: {str(e)}", exc_info=True)
            return False
