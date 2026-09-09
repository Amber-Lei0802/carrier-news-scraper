"""
Main orchestrator — US Carrier Tracker
Scrapes configured news sources → filters for carrier relevance →
deduplicates by URL → saves raw JSON → generates AI briefing (Markdown).

Run: python -m scraper.main
"""
import os
import sys
import yaml
from pathlib import Path

# Project root — resolve from __file__ (works for both direct run and -m)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env — try ROOT first, fall back to CWD
from dotenv import load_dotenv
_env_path = ROOT / ".env"
if not _env_path.exists():
    _env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)
else:
    load_dotenv()  # default behavior

from scraper.sources import usni_news, lockheed_martin, us_navy_news, navy_times
from scraper.filters import is_carrier_related
from storage.local_store import (
    ensure_dirs,
    load_seen_urls,
    save_seen_urls,
    save_raw_items,
    save_report,
    dedupe_by_url,
)


def load_config() -> dict:
    config_path = ROOT / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def collect_all(config: dict) -> list[dict]:
    """Fetch from all enabled sources."""
    sources_cfg = config.get("sources", [])
    all_items = []

    source_map = {
        "USNI News": usni_news.fetch,
        "Lockheed Martin": lockheed_martin.fetch,
        "US Navy News": us_navy_news.fetch,
        "Navy Times": navy_times.fetch,
    }

    for src in sources_cfg:
        name = src.get("name", "")
        if not src.get("enabled", True):
            print(f"  [{name}] Disabled — skipping")
            continue

        fetch_fn = source_map.get(name)
        if not fetch_fn:
            print(f"  [{name}] Unknown source — skipping")
            continue

        print(f"  [{name}] Fetching...")
        try:
            items = fetch_fn()
            print(f"  [{name}] Got {len(items)} items")
            all_items.extend(items)
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")

    return all_items


def filter_carrier(items: list[dict], config: dict) -> list[dict]:
    """Keep only carrier-related items."""
    carrier_items = []
    for item in items:
        is_match, count, matched = is_carrier_related(item, config)
        if is_match:
            item["_carrier_keywords"] = matched
            item["_match_count"] = count
            carrier_items.append(item)

    print(f"  [Filter] {len(items)} total → {len(carrier_items)} carrier-related")
    return carrier_items


def ai_enabled() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def main():
    print("=" * 60)
    print("US Carrier Tracker — Daily Run")
    print("=" * 60)

    config = load_config()
    ensure_dirs(config)

    # Step 1: Load seen URLs for deduplication
    seen_urls = load_seen_urls(config)
    print(f"\n[Dedup] {len(seen_urls)} URLs already in history")

    # Step 2: Collect from all sources
    print("\n[1/4] Collecting from sources...")
    all_items = collect_all(config)
    print(f"  Total raw items: {len(all_items)}")

    if not all_items:
        print("\nNo items collected — exiting.")
        return

    # Step 3: Filter for carrier relevance
    print("\n[2/4] Filtering for aircraft carrier news...")
    carrier_items = filter_carrier(all_items, config)

    if not carrier_items:
        print("\nNo carrier-related news found in this run — exiting.")
        return

    # Step 4: Deduplicate against seen URLs
    print("\n[3/4] Deduplicating...")
    new_items = dedupe_by_url(carrier_items, seen_urls)
    print(f"  {len(carrier_items)} carrier items → {len(new_items)} new (not seen before)")

    if not new_items:
        print("\nNo new carrier items — skipping report generation.")
        return

    # Step 5: Save raw data
    print("\n[4/4] Saving raw data...")
    raw_path = save_raw_items(new_items, config)
    print(f"  Raw data saved to: {raw_path}")

    # Update seen URLs
    new_urls = [i.get("url", "") for i in new_items if i.get("url")]
    save_seen_urls(config, new_urls)
    print(f"  Added {len(new_urls)} new URLs to seen history")

    # Step 6: AI briefing generation
report = ""
if ai_enabled():
    print("\n[AI] Generating carrier briefing...")
    from ai.briefing import generate_carrier_briefing

    report = generate_carrier_briefing(new_items, config)
    if report:
        print("[AI] AI summary generated successfully")
    else:
        print(" Report generation failed or returned empty. Building fallback simple report.")

# 兜底：AI调用失败时，直接生成简易新闻清单
if not report:
    report = "# US Carrier News Briefing (AI Summary Failed)\n\n"
    for item in new_items:
        title = item.get("title", "No Title")
        url = item.get("url", "#")
        report += f"- [{title}]({url})\n\n"

# 无论AI成功与否，都会保存报告
report_path = save_report(report, config)
print(f" Report saved to: {report_path}")

    print("\n" + "=" * 60)
    print(f"Done — {len(new_items)} new carrier items collected.")
    print("=" * 60)


if __name__ == "__main__":
    main()
