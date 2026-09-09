"""
Navy Times source — gathers news from https://www.navytimes.com/
Method: RSS feed + HTML detail page scraping
Navy Times is a leading independent military news outlet with strong
Navy coverage. Its RSS feed is reliable and frequently updated.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RSS_URL = "https://www.navytimes.com/arc/outboundfeeds/rss/category/news/?outputType=xml"


def fetch(max_items: int = 25) -> list[dict]:
    """
    Fetch latest articles from Navy Times RSS feed.

    Returns list of items with schema:
        name, url, source, date_found, summary, full_text
    """
    results = []

    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Navy Times] RSS fetch failed: {e}")
        return results

    feed = feedparser.parse(resp.text)
    entries = feed.entries[:max_items]

    if not entries:
        print("[Navy Times] RSS returned 0 entries")
        return results

    for entry in entries:
        url = entry.get("link", "").strip()
        if not url:
            continue

        pub_date = _parse_date(entry)

        # Extract summary — RSS description often has HTML
        summary = entry.get("summary", "").strip()
        if summary:
            summary = BeautifulSoup(summary, "html.parser").get_text(strip=True)

        item = {
            "name": entry.get("title", "").strip(),
            "url": url,
            "source": "Navy Times",
            "source_domain": "navytimes.com",
            "date_published": pub_date,
            "date_found": datetime.now(timezone.utc).date().isoformat(),
            "summary": summary,
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


def _parse_date(entry) -> str:
    """Extract published date from RSS entry."""
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
    """Extract main article body from a Navy Times article page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return ""
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Navy Times uses Arc XP platform — common selectors:
    article = (
        soup.select_one("article")
        or soup.select_one("div.article-body")
        or soup.select_one("div#main-content")
        or soup.select_one("div.story")
        or soup.select_one("main")
    )
    if not article:
        article = soup.body or soup

    # Remove non-content elements
    for unwanted in article.select(
        "script, style, nav, header, footer, aside, "
        ".breadcrumb, .share, .related-stories, .sidebar, "
        ".social, .menu, form, .advertisement, .ad, .ads, "
        ".newsletter, .promo, .related, .more-in, "
        ".article-footer, .author-bio, .comments"
    ):
        unwanted.decompose()

    # Get all paragraph text
    paragraphs = article.find_all("p")
    text_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        # Filter out short / boilerplate paragraphs
        if text and len(text) > 25:
            text_parts.append(text)

    full_text = "\n\n".join(text_parts)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    return full_text
