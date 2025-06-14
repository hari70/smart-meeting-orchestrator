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
        
    async def send_message(self, to_number: str, message: str, first_name: str = "User", last_name: str = "") -> bool:
        """Send SMS message via Surge API"""
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
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info(f"SMS sent successfully to {to_number}")
                return True
            else:
                logger.error(f"Failed to send SMS: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return False
