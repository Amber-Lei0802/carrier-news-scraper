"""
Lockheed Martin News source — gathers news from
https://news.lockheedmartin.com/news-releases
Method: HTML page scraping (primary) + RSS fallback
Lockheed Martin's news site works reliably via direct HTML fetching.
We scrape the news-releases listing page, then pull each article body.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
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

LISTING_URL = "https://news.lockheedmartin.com/news-releases"


def fetch(max_items: int = 20) -> list[dict]:
    """
    Fetch latest news from Lockheed Martin newsroom.
    Primary: HTML listing page. Fallback: RSS.

    Returns list of items with schema:
        name, url, source, date_found, summary, full_text
    """
    results = []

    # Primary: scrape HTML listing page
    entries = _scrape_listing_html(max_items)

    if not entries:
        # Fallback: try RSS
        entries = _try_rss(max_items)

    for entry in entries:
        url = entry.get("url", "").strip()
        title = entry.get("title", "").strip()
        if not url or not title:
            continue

        pub_date = entry.get("date", datetime.now(timezone.utc).date().isoformat())

        item = {
            "name": title,
            "url": url,
            "source": "Lockheed Martin",
            "source_domain": "lockheedmartin.com",
            "date_published": pub_date,
            "date_found": datetime.now(timezone.utc).date().isoformat(),
            "summary": entry.get("summary", "").strip(),
            "full_text": "",
            "tags": [],
        }

        # Fetch full article body
        full_text = _fetch_full_text(url)
        if full_text:
            item["full_text"] = full_text

        results.append(item)
        time.sleep(0.5)

    return results


def _scrape_listing_html(max_items: int) -> list[dict]:
    """Scrape the news-releases listing page for article links."""
    entries = []
    try:
        resp = requests.get(LISTING_URL, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return entries
    except requests.RequestException:
        return entries

    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()

    # Lockheed news release URLs follow pattern:
    # https://news.lockheedmartin.com/YYYY-MM-DD-Article-Title-...
    for link in soup.select("a[href]"):
        href = link.get("href", "")
        title = link.get_text(strip=True)

        if not href or not title or len(title) < 15:
            continue

        # Normalize
        if href.startswith("/"):
            href = urljoin("https://news.lockheedmartin.com/", href)

        # Only keep news release article URLs
        if "news.lockheedmartin.com" not in href:
            continue

        # Skip the listing page itself and non-article pages
        if "/news-releases" in href.rstrip("/") and href.rstrip("/").endswith("news-releases"):
            continue

        # Must look like a dated article URL (e.g. contains 2026-08-30)
        if not re.search(r"/20\d{2}-\d{2}-\d{2}", href):
            continue

        if href in seen:
            continue
        seen.add(href)

        # Try to extract date from URL
        date_match = re.search(r"/(\d{4}-\d{2}-\d{2})", href)
        date_str = date_match.group(1) if date_match else ""

        entries.append({
            "url": href,
            "title": title,
            "date": date_str,
            "summary": "",
        })

        if len(entries) >= max_items:
            break

    return entries


def _try_rss(max_items: int) -> list[dict]:
    """Fallback: try RSS feed if HTML scraping fails."""
    import feedparser

    feed_urls = [
        "https://news.lockheedmartin.com/2024-news-releases?rss=1",
        "https://news.lockheedmartin.com/rss/news-releases.xml",
    ]

    for furl in feed_urls:
        try:
            resp = requests.get(furl, headers=HEADERS, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                feed = feedparser.parse(resp.text)
                if feed.entries:
                    entries = []
                    for e in feed.entries[:max_items]:
                        entries.append({
                            "url": e.get("link", ""),
                            "title": e.get("title", ""),
                            "date": _parse_rss_date(e),
                            "summary": e.get("summary", ""),
                        })
                    return entries
        except requests.RequestException:
            continue
        time.sleep(0.5)

    return []


def _parse_rss_date(entry) -> str:
    """Extract date from RSS entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                pass
    return datetime.now(timezone.utc).date().isoformat()


def _fetch_full_text(url: str) -> str:
    """Extract main article body from a Lockheed Martin news page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return ""
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try multiple common content containers
    article = (
        soup.select_one("main")
        or soup.select_one("div#content")
        or soup.select_one("div.article-body")
        or soup.select_one("div.news-release-body")
        or soup.select_one("article")
    )
    if not article:
        article = soup.body or soup

    # Remove non-content elements
    for unwanted in article.select(
        "script, style, nav, header, footer, aside, "
        ".breadcrumb, .share, .related, .sidebar, "
        ".social, .menu, form, .header-cta, "
        ".newsletter-signup, .promo, .card-list-nav"
    ):
        unwanted.decompose()

    # Get all paragraph text
    paragraphs = article.find_all("p")
    text_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        # Filter out very short / boilerplate paragraphs
        if text and len(text) > 25:
            text_parts.append(text)

    full_text = "\n\n".join(text_parts)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    return full_text
