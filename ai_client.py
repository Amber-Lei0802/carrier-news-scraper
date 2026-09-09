"""
ai_client.py - 大模型调用模块
支持 Gemini / OpenAI 两种 provider，自动降级
所有密钥从环境变量读取，禁止硬编码
"""

import os
import json
import time
import requests
import yaml
from pathlib import Path


# Gemini 模型降级链（按优先级排序）
GEMINI_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-lite-latest",
]

_last_call_time = 0.0


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────
#  Gemini 调用
# ──────────────────────────────────────────────
def _call_gemini(prompt: str, api_key: str, model: str = "",
                 rate_limit: float = 7.0) -> str:
    """
    调用 Gemini API，自动降级
    返回纯文本结果，失败返回空字符串
    """
    global _last_call_time
    models = [model] + [m for m in GEMINI_FALLBACK if m != model] if model else GEMINI_FALLBACK[:]

    for m in models:
        # 速率控制
        elapsed = time.time() - _last_call_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)

        url = (
            f"https://generativelanguage.googleapis.com/v1beta"
            f"/models/{m}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 4096,
            },
        }

        try:
            _last_call_time = time.time()
            resp = requests.post(url, json=payload, timeout=60)

            if resp.status_code == 200:
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                if text.strip():
                    print(f"  [AI] Gemini 模型 {m} 调用成功")
                    return text.strip()

            if resp.status_code in (429, 503):
                print(f"  [AI] Gemini {m} 限流，尝试下一个模型...")
                time.sleep(2)
                continue

            print(f"  [AI] Gemini {m} 返回 {resp.status_code}，尝试下一个...")

        except requests.RequestException as e:
            print(f"  [AI] Gemini {m} 网络异常: {e}")
            time.sleep(1)
            continue

    return ""


# ──────────────────────────────────────────────
#  OpenAI 兼容接口调用
# ──────────────────────────────────────────────
def _call_openai(prompt: str, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1") -> str:
    """
    调用 OpenAI 兼容 API（也支持第三方中转）
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一名专业的军事新闻分析师，擅长撰写简洁准确的情报简报。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 4096,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content.strip():
                print(f"  [AI] OpenAI 模型 {model} 调用成功")
                return content.strip()
        print(f"  [AI] OpenAI 返回 {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"  [AI] OpenAI 网络异常: {e}")

    return ""


# ──────────────────────────────────────────────
#  统一生成简报入口
# ──────────────────────────────────────────────
def generate_briefing(news_items: list[dict], config: dict = None) -> str:
    """
    将新闻列表交给大模型生成 Markdown 简报
    返回: Markdown 格式的简报文本
    """
    if config is None:
        config = load_config()

    ai_cfg = config.get("ai", {})
    provider = ai_cfg.get("provider", "gemini")
    report_cfg = config.get("report", {})
    language = report_cfg.get("language", "zh-CN")

    # 构建新闻摘要文本
    news_text_parts = []
    for i, item in enumerate(news_items, 1):
        desc = item.get("description", "")
        pub_date = item.get("pub_date", "")
        news_text_parts.append(
            f"[{i}] {item['title']}\n"
            f"    来源: {item['source']} | 时间: {pub_date or item.get('date_found', '未知')}\n"
            f"    摘要: {desc[:300] if desc else '无摘要'}\n"
            f"    链接: {item['url']}"
        )
    news_text = "\n\n".join(news_text_parts)

    # Prompt 模板
    if language == "zh-CN":
        prompt = f"""你是一名专业的国际军事分析师，请根据以下新闻信息，撰写一份「美国航母每日动态简报」。

要求：
1. 使用中文撰写，语言简洁专业
2. 按主题分类整理（如：部署动态、军事演习、维护保养、人事变动、政策与战略等）
3. 每条新闻用 1-2 句话概括核心内容
4. 在末尾提供「综合态势评估」，总结当日航母整体动态趋势
5. 标注信息来源

输出格式为 Markdown，结构如下：
# 🚢 美国航母每日动态简报
> 日期：YYYY-MM-DD

## 📌 今日要闻
（最重要的 1-3 条动态）

## 📋 分类动态
### 部署与调动
### 演习与训练
### 维护与保障
### 政策与战略
### 其他动态

## 📊 综合态势评估
（2-3 句话的整体判断）

---
*数据来源：自动抓取公开新闻 | 生成时间：YYYY-MM-DD HH:MM UTC*

以下是今日抓取到的新闻（共 {len(news_items)} 条）：

{news_text}"""
    else:
        prompt = f"""You are a professional military analyst. Based on the following news, write a "US Aircraft Carrier Daily Briefing".

Requirements:
1. Write in English, concise and professional
2. Categorize by topic (deployments, exercises, maintenance, policy, etc.)
3. 1-2 sentences per item
4. End with an overall situation assessment
5. Cite sources

Output in Markdown format.

Here are today's news items ({len(news_items)} total):

{news_text}"""

    # 调用大模型
    if provider == "gemini":
        api_key = os.environ.get(ai_cfg.get("gemini", {}).get("api_key_env", "GEMINI_API_KEY"), "")
        if not api_key:
            print("[AI] 错误: GEMINI_API_KEY 未设置")
            return _fallback_report(news_items)
        rate_limit = ai_cfg.get("gemini", {}).get("rate_limit_seconds", 7)
        result = _call_gemini(prompt, api_key, rate_limit=rate_limit)

    elif provider == "openai":
        api_key = os.environ.get(ai_cfg.get("openai", {}).get("api_key_env", "OPENAI_API_KEY"), "")
        if not api_key:
            print("[AI] 错误: OPENAI_API_KEY 未设置")
            return _fallback_report(news_items)
        model = ai_cfg.get("openai", {}).get("model", "gpt-4o-mini")
        base_url = os.environ.get(
            ai_cfg.get("openai", {}).get("base_url_env", "OPENAI_BASE_URL"),
            "https://api.openai.com/v1"
        )
        result = _call_openai(prompt, api_key, model=model, base_url=base_url)

    else:
        print(f"[AI] 不支持的 provider: {provider}")
        return _fallback_report(news_items)

    if result:
        return result

    print("[AI] 所有模型调用失败，使用降级报告")
    return _fallback_report(news_items)


def _fallback_report(news_items: list[dict]) -> str:
    """大模型不可用时的降级报告，纯格式化输出"""
    today = time.strftime("%Y-%m-%d")
    lines = [
        f"# 🚢 美国航母每日动态简报",
        f"> 日期：{today}",
        f"",
        f"⚠️ **注意：AI 模型调用失败，以下为原始新闻列表（未分析）**",
        f"",
    ]
    for i, item in enumerate(news_items[:20], 1):
        lines.append(f"### {i}. {item['title']}")
        lines.append(f"- 来源: {item['source']}")
        if item.get("pub_date"):
            lines.append(f"- 时间: {item['pub_date']}")
        if item.get("description"):
            lines.append(f"- 摘要: {item['description'][:200]}")
        lines.append(f"- 链接: {item['url']}")
        lines.append("")

    lines.append("---")
    lines.append(f"*降级报告 | {today}*")
    return "\n".join(lines)


# 独立运行时测试
if __name__ == "__main__":
    sample = [
        {"title": "USS Ford deploys to Mediterranean", "url": "https://example.com/1",
         "source": "Test", "date_found": "2025-01-01", "pub_date": "Mon, 01 Jan 2025",
         "description": "The USS Gerald R. Ford has been deployed to the Mediterranean Sea."},
    ]
    print(generate_briefing(sample))
