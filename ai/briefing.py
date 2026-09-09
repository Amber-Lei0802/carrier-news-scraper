"""
AI Report Pipeline — synthesizes multiple carrier-related news items
into a single integrated defense intelligence briefing.

Unlike the standard per-item enrichment, this pipeline:
1. Takes ALL carrier news from a single run
2. Sends them in one prompt to Gemini
3. Produces one consolidated Markdown report
4. Cites all sources with links at the end
"""
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

from ai.client import generate


def generate_carrier_briefing(
    items: list[dict],
    config: dict,
) -> str:
    """
    Generate an integrated carrier news briefing from multiple sources.

    Args:
        items: List of carrier-related news items (each with full_text).
        config: Full config dict from config.yaml.

    Returns:
        Complete Markdown report as a string. Empty string on failure.
    """
    if not items:
        return ""

    ai_config = config.get("ai", {})
    model = ai_config.get("model", "gemini-2.5-flash")
    rate_limit = ai_config.get("rate_limit_seconds", 8)
    max_tokens = ai_config.get("max_output_tokens", 4096)
    temperature = ai_config.get("temperature", 0.3)
    max_items = ai_config.get("max_items_per_report", 50)

    # Cap items to stay within context
    items = items[:max_items]

    print(f"  [AI] Generating carrier briefing from {len(items)} items...")

    prompt = _build_briefing_prompt(items)

    result = generate(
        prompt,
        model=model,
        rate_limit=rate_limit,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    # The expected output is Markdown text (not JSON)
    if not result:
        print("  [AI] Report generation failed — empty response")
        return ""

    report_text = result.get("text", "")
    if not report_text:
        # If it came back as a JSON dict with a "report" or similar key, try to extract
        report_text = result.get("report", "") or json.dumps(result, ensure_ascii=False, indent=2)

    return report_text.strip()


def _build_briefing_prompt(items: list[dict]) -> str:
    """
    Build the prompt for the integrated carrier briefing (Chinese output).

    Strict constraints:
    - Use ONLY provided news material — no fabrication
    - Note conflicts between sources with attribution
    - Structure: overview → per-carrier updates → program/industry → assessment → sources
    - Tone: formal, objective, defense intelligence briefing style
    - Language: Simplified Chinese
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build indexed item list
    items_text = ""
    for i, item in enumerate(items, 1):
        title = item.get("name", "Untitled")
        source = item.get("source", "Unknown")
        url = item.get("url", "")
        pub_date = item.get("date_published", "")
        body = item.get("full_text", "") or item.get("summary", "")
        # Truncate very long bodies to fit context
        if len(body) > 3000:
            body = body[:3000] + "\n...[truncated]"

        items_text += f"""--- 新闻条目 #{i} ---
标题：{title}
来源：{source}
链接：{url}
发布日期：{pub_date}
正文内容：
{body}

"""

    prompt = f"""你是一名资深国防情报分析师。请**仅基于以下提供的英文新闻素材**，撰写一份简明、客观的美国航空母舰动态情报简报。

## 报告日期
{today}

## 严格规则（必须遵守）
1. **只使用所提供新闻素材中的信息**。不得添加任何源材料中没有的事实、时间线或分析。
   不得引用外部知识或源材料中未提及的历史事件。
2. **如果不同来源存在信息冲突**，必须明确指出分歧，并分别标注信息来源
   （例如："据USNI新闻报道……，而美国海军官方声明称……"）。
3. **每一项事实陈述都必须可追溯至至少一个来源**。
4. **不得使用情绪化语言、推测或评论**。严格按照来源陈述内容，不做主观判断。
5. **输出语言：简体中文**。使用标准防务术语（如：航母打击群、部署、换料复合大修RCOH、
   计划增量可用性PSA、海试、入坞、前沿部署、母港等）。
6. 专有名词（舰名、人名、地名）首次出现时保留英文原名，如："亚伯拉罕·林肯号（USS Abraham Lincoln, CVN-72）"。
7. 最后一部分必须是编号的引用来源列表。

## 报告结构（请严格使用以下章节标题，共五章）

### 一、航母总体态势
（综合概述：本期提到多少艘航母，整体运行节奏如何——部署、维护、试航等。2-4句话。）

### 二、各航母动态
（对于来源中提到的每一艘航空母舰，按舰名分节，以要点形式整理其当前状态、部署位置、
部署阶段、维修周期、海试或项目进展。如同一艘航母被多个来源提及，进行整合，并注明差异之处。）

### 三、项目与工业进展
（涵盖与航母项目相关的新合同、技术进展、造船里程碑、福特级项目更新、
以及洛克希德·马丁等军工企业发布的航母相关消息。）

### 四、简要评估
（客观陈述本报告期内最具作战意义的2-3点动态总结。不做推测——仅对来源信息进行加权归纳。）

### 五、引用来源
（报告中实际引用或参考的所有新闻链接的编号列表，附来源名称和文章标题。格式：
`1. 【来源名称】文章标题 — URL`）

---

## 待分析新闻素材

{items_text}

---

## 输出格式
输出一份完整的 Markdown 文档。不要把整个输出包在代码块里。
严格使用上述指定的五个中文章节标题。
所有正文内容使用简体中文。
"""

    return prompt
