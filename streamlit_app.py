# streamlit_app.py
import streamlit as st
import sqlite3
import requests
import feedparser
import json
from bs4 import BeautifulSoup
import openai

# --- 1. AUTO-GENERATED SOURCES ---
EVENTBRITE_CATEGORIES = [
    "hackathon", "technology", "artificial-intelligence", "data-science",
    "machine-learning", "cybersecurity", "blockchain", "web-development",
    "conference", "webinar", "workshop"
]
EVENTBRITE_LOCATIONS = [
    "online", "ireland--dublin", "united-kingdom--london",
    "united-states--new-york", "united-states--san-francisco",
    "canada--toronto", "australia--sydney"
]
# ~77 Eventbrite feeds
EB_FEEDS = [
    f"https://www.eventbrite.com/d/{loc}/{cat}--events/rss/"
    for loc in EVENTBRITE_LOCATIONS
    for cat in EVENTBRITE_CATEGORIES
]

# 9 More sources (RSS or URL|CSS)
STATIC_SOURCES = [
    "https://devpost.com/hackathons|.tile .project-title a",
    "https://devpost.com/challenges|.challenge-title a",
    "https://www.hackerearth.com/challenges/rss/",
    "https://www.meetup.com/topics/hackathon/rss/",
    "https://www.meetup.com/topics/technology/rss/",
    "https://mlh.io/seasons/2025/events|.event-card a",
    "https://www.kaggle.com/competitions.rss",
    "https://www.f6s.com/events/rss",
    "https://confs.tech/feed.xml"
]

SOURCES = EB_FEEDS + STATIC_SOURCES

# --- 2. HELPERS ---

def init_db():
    conn = sqlite3.connect("events.db")
    conn.execute("""
      CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT,
        date TEXT,
        location TEXT,
        url TEXT,
        notified INTEGER DEFAULT 0
      )
    """)
    conn.commit()
    conn.close()

def fetch_rss(url):
    feed = feedparser.parse(url)
    return [{
        "id": entry.id,
        "title": entry.title,
        "description": entry.get("summary",""),
        "url": entry.link
    } for entry in feed.entries]

def scrape_site(url, selector):
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for a in soup.select(selector):
        link = a.get("href")
        if link:
            items.append({"id": link, "title": a.get_text(strip=True), "url": link})
    return items

def extract_metadata(ev, openai_key):
    openai.api_key = openai_key
    prompt = (
        f"Title: {ev['title']}\n"
        f"Description: {ev.get('description','')}\n\n"
        "Extract JSON with fields: date (YYYY-MM-DD), "
        "location (Online or In-Person), topics (list of keywords)."
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )
    return json.loads(resp.choices[0].message.content)

def matches(meta, interests, formats, types, user_location):
    # 1) topic overlap
    if not set(meta.get("topics",[])) & set(interests):
        return False
    # 2) format filter
    if meta.get("location","").lower() not in [f.lower() for f in formats]:
        return False
    # 3) location filter
    if user_location and user_location.lower() not in meta.get("location","").lower():
        return False
    # 4) type keyword in title
    title = meta.get("title","").lower()
    return any(t.lower() in title for t in types)

def send_slack(msg, webhook_url):
    requests.post(webhook_url, json={"text": msg}, timeout=5)

# --- 3. STREAMLIT UI ---

st.title("📅 Event Opportunity Scout")

st.sidebar.header("🔑 Credentials")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
slack_webhook = st.sidebar.text_input("Slack Webhook URL", type="password")

st.sidebar.header("⚙️ User Filters")
interests = st.sidebar.text_input(
    "Interests (comma-separated)", "AI, Web Development, IoT"
).split(",")
location = st.sidebar.text_input("Location filter (e.g. Dublin)", "Dublin")
formats = st.sidebar.multiselect(
    "Event Formats", ["online","in-person"], default=["online","in-person"]
)
event_types = st.sidebar.multiselect(
    "Event Types", 
    ["Hackathon","Conference","Workshop","Webinar","Meetup"], 
    default=["Hackathon","Conference","Workshop","Webinar","Meetup"]
)

# Initialize DB on first run
init_db()

if st.button("Fetch & Match Events"):
    if not openai_key or not slack_webhook:
        st.error("Enter both API keys in the sidebar.")
    else:
        conn = sqlite3.connect("events.db")
        c = conn.cursor()
        for src in SOURCES:
            try:
                evs = (scrape_site(*src.split("|",1))
                       if "|" in src else fetch_rss(src))
                for ev in evs:
                    meta = extract_metadata(ev, openai_key)
                    meta["title"] = ev["title"]
                    if matches(meta, interests, formats, event_types, location):
                        c.execute(
                          "INSERT OR IGNORE INTO events "
                          "(id,title,date,location,url) VALUES (?,?,?,?,?)",
                          (ev["id"], ev["title"], meta["date"],
                           meta["location"], ev["url"])
                        )
            except Exception as e:
                st.warning(f"Source failed: {src} → {e}")
        conn.commit()
        conn.close()
        st.success("Fetched & matched!")

# Show un-notified events
conn = sqlite3.connect("events.db")
rows = conn.execute("SELECT * FROM events WHERE notified=0").fetchall()
conn.close()

if rows:
    st.subheader("🔔 Unnotified Events")
    for r in rows:
        st.markdown(f"- **{r[1]}** on {r[2]} ({r[3]}) — [Link]({r[4]})")
    if st.button("Send Slack Notifications"):
        for r in rows:
            send_slack(f"New event: *{r[1]}* — {r[4]}", slack_webhook)
        conn = sqlite3.connect("events.db")
        conn.execute("UPDATE events SET notified=1 WHERE notified=0")
        conn.commit()
        conn.close()
        st.success("Notifications sent!")
else:
    st.info("No new events to notify.")
