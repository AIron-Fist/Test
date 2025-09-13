from config import load_config

cfg = load_config()

def is_relevant(metadata):
    interests = set(cfg["user_profile"]["interests"])
    topics = set(metadata.get("topics", []))
    return bool(interests & topics)
