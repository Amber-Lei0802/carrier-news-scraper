"""
US Navy News source — gathers news from https://www.navy.mil/News/
Method: RSS feed + HTML detail page scraping
The US Navy site provides RSS feeds for its news sections.
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

# US Navy news RSS feeds — try multiple endpoints
FEED_URLS = [
    "https://www.navy.mil/News/RSS/",
    "https://www.navy.mil/feeds/rss.xml",
    "https://www.navy.mil/News/?rss=1",
]


def fetch(max_items: int = 30) -> list[dict]:
    """
    Fetch latest news from US Navy official site.
    Returns list of items with schema:
        name, url, source, date_found, summary, full_text
    """
    results = []
    feed_entries = []

    # Try each RSS URL until we get results
    for furl in FEED_URLS:
        try:
            resp = requests.get(furl, headers=HEADERS, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                feed = feedparser.parse(resp.text)
                if feed.entries:
                    feed_entries = feed.entries[:max_items]
                    break
        except requests.RequestException:
            continue
        time.sleep(0.5)

    if not feed_entries:
        # Fallback: scrape the news listing page
        feed_entries = _scrape_listing_page(max_items)

    for entry in feed_entries:
        url = entry.get("link", "").strip()
        if not url:
            continue

        # Normalize relative URLs
        if url.startswith("/"):
            url = urljoin("https://www.navy.mil/", url)

        pub_date = _parse_date(entry)

        item = {
            "name": entry.get("title", "").strip(),
            "url": url,
            "source": "US Navy News",
            "source_domain": "navy.mil",
            "date_published": pub_date,
            "date_found": datetime.now(timezone.utc).date().isoformat(),
            "summary": entry.get("summary", "").strip(),
            "full_text": "",
            "tags": [t.get("term", "") for t in entry.get("tags", [])],
        }

        # Fetch full article body
        full_text = _fetch_full_text(url)
        if full_text:
            item["full_text"] = full_text

        results.append(item)
        time.sleep(0.5)

    return results


def _scrape_listing_page(max_items: int) -> list[dict]:
    """Fallback: scrape the news listing page HTML when RSS is unavailable."""
    entries = []
    try:
        resp = requests.get(
            "https://www.navy.mil/News/",
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            return entries
    except requests.RequestException:
        return entries

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_urls = set()

    # US Navy site uses various list structures — cast a wide net
    for link in soup.select("a[href*='/News/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not href or not title or len(title) < 15:
            continue

        # Skip pagination links
        if "page" in href.lower() or "archive" in href.lower():
            continue

        if href.startswith("/"):
            href = urljoin("https://www.navy.mil/", href)

        if "navy.mil" not in href:
            continue

        if href in seen_urls:
            continue
        seen_urls.add(href)

        entries.append({"link": href, "title": title, "summary": ""})

        if len(entries) >= max_items:
            break

    return entries


def _parse_date(entry) -> str:
    """Extract published date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                pass
    for attr in ("published", "updated"):
        date_str = entry.get(attr, "")
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                return dt.date().isoformat()
            except (ValueError, TypeError):
                pass
    return datetime.now(timezone.utc).date().isoformat()


def _fetch_full_text(url: str) -> str:
    """Extract main article body from a US Navy news page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return ""
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # US Navy news pages: try several common container selectors
    article = (
        soup.select_one("div#content")
        or soup.select_one("div.article-body")
        or soup.select_one("div.story-body")
        or soup.select_one("div.l-content")
        or soup.select_one("main")
        or soup.select_one("article")
    )
    if not article:
        article = soup.body or soup

    # Remove cruft
    for unwanted in article.select(
        "script, style, nav, header, footer, aside, "
        ".breadcrumb, .share, .related, .sidebar, "
        ".social, .menu, form, .byline, .meta-info"
    ):
        unwanted.decompose()

    paragraphs = article.find_all("p")
    text_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if text and len(text) > 20:
            text_parts.append(text)

    full_text = "\n\n".join(text_parts)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    return full_text
