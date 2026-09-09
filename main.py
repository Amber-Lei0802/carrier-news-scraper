"""
main.py - 主入口
编排：抓取新闻 → AI 生成简报 → 保存文件 → 邮件推送
所有密钥从环境变量读取，禁止硬编码
"""

import os
import sys
import time
import yaml
from pathlib import Path
from datetime import datetime, timezone

from scraper import scrape_all
from ai_client import generate_briefing
from email_sender import send_report


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def main():
    """主流程编排"""
    print("=" * 60)
    print("🚢  美国航母每日动态简报 - 自动生成系统")
    print("=" * 60)

    start_time = time.time()
    config = load_config()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_cfg = config.get("report", {})
    output_dir = Path(report_cfg.get("output_dir", "output"))
    max_items = report_cfg.get("max_items", 30)

    # ── 第一步：抓取新闻 ──────────────────────────
    print(f"\n📰 Step 1/4: 抓取新闻 ({today})")
    print("-" * 40)
    news_items = scrape_all(config)

    if not news_items:
        print("\n⚠️  未抓取到任何新闻，终止运行")
        print("   可能原因：网络问题 / RSS 源变更 / 被限流")
        sys.exit(1)

    # 限制最大条数，避免超出大模型 token 限制
    if len(news_items) > max_items:
        print(f"  新闻数 ({len(news_items)}) 超过上限，截取前 {max_items} 条")
        news_items = news_items[:max_items]

    # ── 第二步：AI 生成简报 ────────────────────────
    print(f"\n🤖 Step 2/4: AI 生成简报")
    print("-" * 40)
    report_md = generate_briefing(news_items, config)

    # ── 第三步：保存 Markdown 文件 ─────────────────
    print(f"\n💾 Step 3/4: 保存报告文件")
    print("-" * 40)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_filename = f"carrier_briefing_{today}.md"
    report_path = output_dir / report_filename
    report_path.write_text(report_md, encoding="utf-8")
    print(f"  ✅ 已保存: {report_path} ({len(report_md)} 字符)")

    # ── 第四步：邮件推送 ──────────────────────────
    print(f"\n📧 Step 4/4: 邮件推送")
    print("-" * 40)
    email_cfg = config.get("email", {})
    email_enabled = email_cfg.get("enabled", True)

    if email_enabled:
        send_report(report_md, report_filename, config)
    else:
        print("  ⏭️  邮件推送已关闭 (email.enabled=false)")

    # ── 完成 ──────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"✅  完成！耗时 {elapsed:.1f} 秒")
    print(f"    新闻: {len(news_items)} 条")
    print(f"    报告: {report_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
