import os
import requests
from django.conf import settings
from dotenv import load_dotenv
from django.utils import timezone
from datetime import timedelta

load_dotenv()

class DailyService:
    @staticmethod
    def create_room(room_name, expiration=None):    
        url = f"{os.getenv('DAILY_API_URL')}/rooms"
        headers = {
            "Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}",
            "Content-Type": "application/json"
        }
        payload = {
            "name": room_name,
            "privacy": "private",
            "properties": {
                "exp": expiration or int((timezone.now() + timedelta(hours=1)).timestamp()),
                "enable_recording": "cloud",
                "enable_prejoin_ui": True
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_room(room_name):
        url = f"{os.getenv('DAILY_API_URL')}/rooms/{room_name}"
        headers = {"Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()