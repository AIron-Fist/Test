import requests
from config import load_config

cfg = load_config()

def send_slack(message):
    url = cfg["slack_webhook"]
    payload = {"text": message}
    requests.post(url, json=payload)
