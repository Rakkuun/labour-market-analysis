import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY', '').strip().strip('"').strip("'")

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

url = 'https://openrouter.ai/api/v1/chat/completions'
data = {
    'model': 'openchat/openchat-3.5-0106',
    'messages': [
        {'role': 'user', 'content': 'Wat is het weer vandaag in Amsterdam?'}
    ],
    'max_tokens': 100,
    'temperature': 0.7
}

resp = requests.post(url, headers=headers, json=data, timeout=60)
print('Status:', resp.status_code)
print('Response:', resp.text)
