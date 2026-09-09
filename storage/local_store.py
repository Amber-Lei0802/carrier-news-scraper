"""
Local JSON storage for raw news data and Markdown reports.
Handles deduplication by URL and date-based file organization.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable


def ensure_dirs(config: dict):
    """Ensure storage directories exist."""
    storage_cfg = config.get("storage", {})
    raw_dir = Path(storage_cfg.get("raw_data_dir", "data/raw"))
    reports_dir = Path(storage_cfg.get("reports_dir", "reports"))

    raw_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Also ensure data/ dir for seen_urls
    Path("data").mkdir(parents=True, exist_ok=True)


def load_seen_urls(config: dict) -> set[str]:
    """Load the set of URLs we've already seen (for deduplication)."""
    seen_file = Path(config.get("storage", {}).get("seen_urls_file", "data/seen_urls.json"))
    if seen_file.exists():
        try:
            data = json.loads(seen_file.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def save_seen_urls(config: dict, urls: Iterable[str]):
    """Append new URLs to the seen-urls file (merges with existing)."""
    seen_file = Path(config.get("storage", {}).get("seen_urls_file", "data/seen_urls.json"))
    existing = load_seen_urls(config)
    combined = existing | set(urls)

    seen_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "urls": sorted(combined),
        "count": len(combined),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    seen_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_raw_items(items: list[dict], config: dict) -> Path:
    """
    Save raw carrier-filtered news items to a dated JSON file.

    Returns:
        Path to the saved file.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    storage_cfg = config.get("storage", {})
    raw_dir = Path(storage_cfg.get("raw_data_dir", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    filename = f"carrier_news_{today}.json"
    filepath = raw_dir / filename

    payload = {
        "date": today,
        "source_count": len(set(i.get("source", "") for i in items)),
        "item_count": len(items),
        "items": items,
    }

    filepath.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return filepath


def save_report(report_md: str, config: dict) -> Path:
    """
    Save the AI-generated carrier briefing to a dated Markdown file.

    Returns:
        Path to the saved file.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    storage_cfg = config.get("storage", {})
    reports_dir = Path(storage_cfg.get("reports_dir", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"carrier_briefing_{today}.md"
    filepath = reports_dir / filename

    # Add header if report doesn't have one
    if not report_md.strip().startswith("#"):
        header = f"# 美国航母每日动态简报 — {today}\n\n"
        report_md = header + report_md

    filepath.write_text(report_md, encoding="utf-8")
    return filepath


def dedupe_by_url(items: list[dict], seen_urls: set[str]) -> list[dict]:
    """Filter out items whose URLs are already in seen_urls."""
    new_items = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen_urls:
            new_items.append(item)
    return new_items
