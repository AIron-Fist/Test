import feedparser
from bs4 import BeautifulSoup
import requests

def fetch_rss(rss_url):
    feed = feedparser.parse(rss_url)
    return [{
      "id": entry.id,
      "title": entry.title,
      "description": entry.summary,
      "url": entry.link
    } for entry in feed.entries]

def scrape_site(url, selector):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    return [{
      "id": a["href"],
      "title": a.text,
      "url": a["href"]
    } for a in soup.select(selector)]
