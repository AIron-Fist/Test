import openai
from config import load_config

cfg = load_config()
openai.api_key = cfg["openai_key"]

def extract_metadata(event):
    prompt = (
      f"Extract date, location (online/offline), and topics from:\n"
      f"{event['title']} - {event.get('description','')}\n"
      "Return JSON with keys date, location, topics."
    )
    resp = openai.ChatCompletion.create(
      model="gpt-4o-mini",
      messages=[{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content
