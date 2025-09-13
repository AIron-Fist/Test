import streamlit as st
from config import load_config
from scraper import fetch_rss, scrape_site
from parser import extract_metadata
from matcher import is_relevant
from notifier import send_slack
from db import get_conn

st.title("Event Opportunity Scout")

# Load & edit config
cfg = load_config()
st.sidebar.header("User Profile")
cfg["openai_key"] = st.sidebar.text_input("OpenAI API Key", cfg["openai_key"])
cfg["slack_webhook"] = st.sidebar.text_input("Slack Webhook URL", cfg["slack_webhook"])
cfg["user_profile"]["interests"] = st.sidebar.text_input(
    "Interests (comma-separated)",
    ", ".join(cfg["user_profile"]["interests"])
).split(",")

# Manage sources
st.sidebar.header("Sources")
sources = cfg.get("sources", [])
new_src = st.sidebar.text_input("Add RSS or URL|selector (e.g. feed_url OR url|.css)")
if st.sidebar.button("Add Source"):
    sources.append(new_src.strip())
    cfg["sources"] = sources

if st.sidebar.button("Save Config"):
    with open("config.json","w") as f:
        f.write(st.sidebar.session_state["config_text"])
    st.sidebar.success("Config saved!")

# Main actions
if st.button("Fetch & Match Events"):
    conn = get_conn()
    c = conn.cursor()
    for src in sources:
        if "|" in src:
            url, selector = src.split("|",1)
            events = scrape_site(url, selector)
        else:
            events = fetch_rss(src)
        for ev in events:
            meta = eval(extract_metadata(ev))
            if is_relevant(meta):
                c.execute("""
                  INSERT OR IGNORE INTO events (id,title,date,location,url)
                  VALUES (?,?,?,?,?)
                """, (ev["id"], ev["title"], meta["date"], meta["location"], ev["url"]))
    conn.commit()
    conn.close()
    st.success("Events fetched and stored.")

# Display stored events
conn = get_conn()
df = conn.execute("SELECT * FROM events WHERE notified=0").fetchall()
conn.close()
if df:
    st.subheader("Unnotified Events")
    for row in df:
        st.markdown(f"- **{row['title']}** ({row['date']}, {row['location']}) – [Link]({row['url']})")
    if st.button("Send Notifications"):
        for row in df:
            send_slack(f"New event: {row['title']} – {row['url']}")
        conn = get_conn()
        conn.execute("UPDATE events SET notified=1 WHERE notified=0")
        conn.commit()
        conn.close()
        st.success("Notifications sent.")
else:
    st.info("No new events.")

