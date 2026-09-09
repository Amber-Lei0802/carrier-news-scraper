"""
USNI News source — gathers news from https://news.usni.org/
Method: RSS feed + HTML detail page scraping
USNI provides an RSS feed at /feed/ which is the cleanest entry point.
We then fetch each article's full HTML body for the writing material.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; US-Carrier-Tracker/1.0; research bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

FEED_URL = "https://news.usni.org/feed"


def fetch(max_items: int = 30) -> list[dict]:
    """
    Fetch latest articles from USNI News RSS feed.
    Returns list of items with schema:
        name, url, source, date_found, summary, full_text
    """
    results = []
    try:
        resp = requests.get(FEED_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[USNI] Feed fetch failed: {e}")
        return results

    feed = feedparser.parse(resp.text)
    entries = feed.entries[:max_items]

    for entry in entries:
        url = entry.get("link", "").strip()
        if not url:
            continue

        # Parse date
        pub_date = _parse_date(entry)

        item = {
            "name": entry.get("title", "").strip(),
            "url": url,
            "source": "USNI News",
            "source_domain": "news.usni.org",
            "date_published": pub_date,
            "date_found": datetime.now(timezone.utc).date().isoformat(),
            "summary": entry.get("summary", "").strip(),
            "full_text": "",  # populated below
            "tags": [t.get("term", "") for t in entry.get("tags", [])],
        }

        # Fetch full article body
        full_text = _fetch_full_text(url)
        if full_text:
            item["full_text"] = full_text

        results.append(item)
        time.sleep(0.5)  # polite delay

    return results


def _parse_date(entry) -> str:
    """Try to extract published date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                pass
    # Fallback: try string parsing
    for attr in ("published", "updated"):
        date_str = entry.get(attr, "")
        if date_str:
            try:
                # RFC 822 / RFC 2822 common in RSS
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                return dt.date().isoformat()
            except (ValueError, TypeError):
                pass
    return datetime.now(timezone.utc).date().isoformat()


def _fetch_full_text(url: str) -> str:
    """Fetch and extract the main article body from a USNI article page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return ""
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # USNI articles typically have content inside div.entry-content or article
    article = soup.select_one("div.entry-content") or soup.select_one("article")
    if not article:
        article = soup.body or soup

    # Remove unwanted elements
    for unwanted in article.select(
        "script, style, nav, .sharedaddy, .jp-relatedposts, "
        ".post-nav, .author-box, .comment-list, #comments, "
        "aside, .advertisement, .ad, footer"
    ):
        unwanted.decompose()

    # Get text from paragraphs
    paragraphs = article.find_all("p")
    text_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if text and len(text) > 20:  # skip very short / nav links
            text_parts.append(text)

    full_text = "\n\n".join(text_parts)

    # Clean up excessive whitespace
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    return full_text
