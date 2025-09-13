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

EB_FEEDS = [
    f"https://www.eventbrite.com/d/{loc}/{cat}--events/rss/"
    for loc in EVENTBRITE_LOCATIONS
    for cat in EVENTBRITE_CATEGORIES
]

STATIC_SOURCES = [
    "https://devpost.com/hackathons|.challenge-title a",
    "https://devpost.com/challenges|.challenge-title a",
    "https://www.hackerearth.com/challenges/rss/",
    "https://www.meetup.com/topics/technology/rss/",
    "https://www.meetup.com/topics/hackathon/rss/",
    "https://mlh.io/seasons/2025/events|.event-card a",
    "https://www.kaggle.com/competitions.rss",
    "https://www.f6s.com/events/rss",
    "https://confs.tech/feed.xml"
]

SOURCES = EB_FEEDS + STATIC_SOURCES

# --- 2. HELPERS ---

def init_db():
    conn = sqlite3.connect("events.db", check_same_thread=False)
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
    items = []
    for entry in feed.entries:
        items.append({
            "id": entry.id or entry.link,
            "title": entry.title,
            "description": entry.get("summary", ""),
            "url": entry.link
        })
    return items

def scrape_site(url, selector):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for a in soup.select(selector):
        link = a.get("href")
        text = a.get_text(strip=True)
        if link and text:
            items.append({"id": link, "title": text, "url": link})
    return items

def extract_metadata(event, openai_key):
    openai.api_key = openai_key
    prompt = (
        f"Title: {event['title']}\n"
        f"Description: {event.get('description','')}\n\n"
        "Extract JSON with fields:\n"
        "- date (YYYY-MM-DD)\n"
        "- location (Online or In-Person)\n"
        "- topics (list of keywords)\n"
        "Return only the JSON object."
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(resp.choices[0].message.content)

def matches(meta, interests, formats, types, user_location):
    # Topic overlap
    if not set(meta.get("topics", [])) & set(interests):
        return False
    # Format filter (substring match)
    if formats:
        loc_str = meta.get("location", "").lower()
        if not any(fmt.lower() in loc_str for fmt in formats):
            return False
    # Location filter (skip if blank)
    if user_location:
        if user_location.lower() not in meta.get("location", "").lower():
            return False
    # Event type keyword in title
    title = meta.get("title", "").lower()
    if types:
        if not any(t.lower() in title for t in types):
            return False
    return True

def send_slack(message, webhook_url):
    requests.post(webhook_url, json={"text": message}, timeout=5)

# --- 3. STREAMLIT UI ---

st.title("📅 Event Opportunity Scout")

st.sidebar.header("🔑 Credentials")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
slack_webhook = st.sidebar.text_input("Slack Webhook URL", type="password")

st.sidebar.header("⚙️ User Filters")
interests = st.sidebar.text_input(
    "Interests (comma-separated)", "AI, Web Development, IoT"
).split(",")
location_filter = st.sidebar.text_input("Location filter (leave blank for global)", "")
formats = st.sidebar.multiselect(
    "Event Formats", ["online", "in-person"], default=["online", "in-person"]
)
event_types = st.sidebar.multiselect(
    "Event Types",
    ["Hackathon", "Conference", "Workshop", "Webinar", "Meetup"],
    default=["Hackathon", "Conference", "Workshop", "Webinar", "Meetup"]
)

init_db()

if st.button("Fetch & Match Events"):
    if not openai_key or not slack_webhook:
        st.error("Please enter both OpenAI API Key and Slack Webhook URL.")
    else:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        c = conn.cursor()
        for src in SOURCES:
            try:
                if "|" in src:
                    url, sel = src.split("|", 1)
                    events = scrape_site(url, sel)
                else:
                    events = fetch_rss(src)
            except Exception as e:
                st.warning(f"Failed to fetch {src}: {e}")
                continue

            for ev in events:
                try:
                    meta = extract_metadata(ev, openai_key)
                    meta["title"] = ev["title"]
                    if matches(meta, interests, formats, event_types, location_filter):
                        c.execute(
                            "INSERT OR IGNORE INTO events (id, title, date, location, url) VALUES (?, ?, ?, ?, ?)",
                            (ev["id"], ev["title"], meta["date"], meta["location"], ev["url"])
                        )
                except Exception as e:
                    st.warning(f"Error processing {ev['title']}: {e}")

        conn.commit()
        conn.close()
        st.success("Fetched, parsed, and stored matching events.")

conn = sqlite3.connect("events.db", check_same_thread=False)
rows = conn.execute("SELECT * FROM events WHERE notified=0").fetchall()
conn.close()

if rows:
    st.subheader("🔔 Unnotified Events")
    for r in rows:
        st.markdown(f"- **{r[1]}** on {r[2]} ({r[3]}) — [Link]({r[4]})")
    if st.button("Send Slack Notifications"):
        for r in rows:
            send_slack(f"New event match: *{r[1]}* — {r[4]}", slack_webhook)
        conn = sqlite3.connect("events.db", check_same_thread=False)
        conn.execute("UPDATE events SET notified=1 WHERE notified=0")
        conn.commit()
        conn.close()
        st.success("Notifications sent!")
else:
    st.info("No new events to notify.")
