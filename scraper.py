"""
scraper.py - 新闻抓取模块
从 RSS 源和 HTML 页面抓取美国航母相关新闻
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import time
import yaml
from pathlib import Path


# 浏览器 UA，避免被简单拦截
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


def load_config() -> dict:
    """从 config.yaml 加载配置"""
    config_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def fetch_rss(source: dict, timeout: int = 15, max_retries: int = 2) -> list[dict]:
    """
    抓取单个 RSS 源，返回标准化新闻列表
    每条: {title, url, source, date_found, description}
    """
    name = source["name"]
    url = source["url"]
    results = []

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            # 标准 RSS 2.0 格式
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                desc = item.findtext("description", "").strip()

                if title and link:
                    results.append({
                        "title": title,
                        "url": link,
                        "source": name,
                        "date_found": datetime.now(timezone.utc).date().isoformat(),
                        "pub_date": pub_date,
                        "description": desc[:500],
                    })

            # Atom 格式兼容
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                pub_date = entry.findtext("atom:published", "", ns).strip()
                desc = entry.findtext("atom:summary", "", ns).strip()

                if title and link:
                    results.append({
                        "title": title,
                        "url": link,
                        "source": name,
                        "date_found": datetime.now(timezone.utc).date().isoformat(),
                        "pub_date": pub_date,
                        "description": desc[:500],
                    })

            print(f"  [{name}] RSS 抓取到 {len(results)} 条")
            return results

        except Exception as e:
            if attempt < max_retries:
                print(f"  [{name}] 第{attempt+1}次重试... ({e})")
                time.sleep(2)
            else:
                print(f"  [{name}] RSS 抓取失败: {e}")

    return results


def fetch_html(source: dict, timeout: int = 15, max_retries: int = 2) -> list[dict]:
    """
    抓取 HTML 页面中的新闻链接
    用于 RSS 不可用时的补充抓取
    """
    name = source["name"]
    url = source["url"]
    article_selector = source.get("article_selector", "article")
    title_selector = source.get("title_selector", "h3")
    link_selector = source.get("link_selector", "a")
    results = []

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for card in soup.select(article_selector):
                title_el = card.select_one(title_selector)
                link_el = card.select_one(link_selector)

                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    href = link_el.get("href", "")

                    # 处理相对链接
                    if href and not href.startswith("http"):
                        href = f"https://news.google.com{href}"

                    if title and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "source": name,
                            "date_found": datetime.now(timezone.utc).date().isoformat(),
                            "pub_date": "",
                            "description": "",
                        })

            print(f"  [{name}] HTML 抓取到 {len(results)} 条")
            return results

        except Exception as e:
            if attempt < max_retries:
                print(f"  [{name}] 第{attempt+1}次重试... ({e})")
                time.sleep(2)
            else:
                print(f"  [{name}] HTML 抓取失败: {e}")

    return results


def scrape_all(config: dict = None) -> list[dict]:
    """
    执行全部新闻源的抓取，自动去重
    返回: 去重后的新闻列表
    """
    if config is None:
        config = load_config()

    sources_cfg = config.get("news_sources", {})
    scraping_cfg = config.get("scraping", {})
    timeout = scraping_cfg.get("request_timeout", 15)
    delay = scraping_cfg.get("delay_between_requests", 1.5)
    max_retries = scraping_cfg.get("max_retries", 2)

    all_items = []

    # 1. RSS 源抓取
    for src in sources_cfg.get("rss", []):
        items = fetch_rss(src, timeout=timeout, max_retries=max_retries)
        all_items.extend(items)
        time.sleep(delay)

    # 2. HTML 源抓取
    for src in sources_cfg.get("html", []):
        items = fetch_html(src, timeout=timeout, max_retries=max_retries)
        all_items.extend(items)
        time.sleep(delay)

    # 3. 按 URL 去重
    seen = set()
    unique = []
    for item in all_items:
        url = item.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(item)

    print(f"[Scraper] 总计 {len(all_items)} 条 → 去重后 {len(unique)} 条")
    return unique


# 独立运行时测试
if __name__ == "__main__":
    items = scrape_all()
    for i, item in enumerate(items[:10], 1):
        print(f"\n--- [{i}] {item['title']}")
        print(f"    来源: {item['source']}")
        print(f"    链接: {item['url']}")
