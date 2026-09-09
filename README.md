# US Carrier Tracker — 美国航母每日动态追踪机器人

自动从三个权威信息源采集航空母舰相关新闻，经过关键词过滤和去重后，利用 AI 生成一份结构化的每日防务情报简报。

## 功能特性

- **三源采集**：USNI News、洛克希德·马丁官网、美国海军官方新闻
- **精准过滤**：基于航母关键词（CVN、航母名、Ford-class 等）的双层过滤，自动排除潜艇、驱逐舰等无关内容
- **正文抓取**：不仅抓取标题摘要，还抓取新闻详情页完整正文作为写作素材
- **URL 去重**：已采集过的新闻自动跳过，避免重复
- **AI 综合简报**：基于当天所有新闻素材，生成客观中立的航母动态综合报道（Markdown 格式）
- **日报结构**：总体态势 → 各航母动态 → 项目与工业进展 → 简要评估 → 引用来源
- **每日自动运行**：GitHub Actions 定时执行，开箱即用

## 快速开始

### 本地运行

```bash
# 1. 克隆项目后进入目录
cd us-carrier-tracker

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（可选，不配置则只采集不生成 AI 简报）
cp .env.example .env
# 编辑 .env，填入你的 Gemini API Key
# 获取地址：https://aistudio.google.com/apikey

# 4. 运行
python -m scraper.main
```

### 输出文件

运行后会生成：

```
data/
├── raw/
│   └── carrier_news_2026-09-07.json    # 原始新闻素材（JSON）
└── seen_urls.json                       # 已采集 URL 去重记录

reports/
└── carrier_briefing_2026-09-07.md       # AI 生成的综合简报（Markdown）
```

## 部署到 GitHub Actions（推荐）

零服务器成本，每日自动运行：

### 步骤 1：创建 GitHub 仓库

将整个 `us-carrier-tracker/` 目录推送到一个新的 GitHub 仓库（公开仓库 GitHub Actions 免费）。

### 步骤 2：配置 Secret

在仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Name | Value | 是否必需 |
|---|---|---|
| `GEMINI_API_KEY` | 你的 Gemini API Key | 可选（不填则只采集数据，不生成 AI 简报） |

获取地址：https://aistudio.google.com/apikey （免费额度 500 请求/天）

### 步骤 3：触发运行

- **自动运行**：每天 UTC 12:00（北京时间 20:00）自动执行
- **手动触发**：仓库 **Actions → US Carrier Tracker → Run workflow**

每次运行后，采集的新闻数据和生成的简报会自动提交到仓库中。

## 配置说明

编辑 `config.yaml` 可自定义：

- **关键词过滤**：`filters.carrier_keywords` 增删航母相关关键词
- **屏蔽词**：`filters.blocked_keywords` 排除干扰内容
- **AI 设置**：`ai.model`、`ai.temperature` 等
- **数据源开关**：`sources[].enabled` 启用/停用某个信息源

## 简报结构示例

AI 生成的简报包含以下章节：

1. **Overall Carrier Posture** — 近期航母整体态势总述
2. **Individual Carrier Updates** — 各艘航母部署/维修/海试/项目进展（分点梳理）
3. **Program & Industry Developments** — 项目与军工动态
4. **Brief Assessment** — 客观态势小结
5. **Sources** — 引用来源链接列表

## 数据来源

| 来源 | 类型 | 说明 |
|---|---|---|
| [USNI News](https://news.usni.org/) | 独立防务媒体 | 美国海军研究院下属新闻机构，报道权威详实 |
| [Lockheed Martin News](https://news.lockheedmartin.com/) | 军工企业官网 | 洛克希德·马丁官方新闻发布，关注装备与合同动态 |
| [US Navy News](https://www.navy.mil/News/) | 官方渠道 | 美国海军官方新闻发布，权威官方口径 |

## 注意事项

- 本工具仅用于公开信息的自动化聚合与分析
- 请遵守各网站的 `robots.txt` 和使用条款
- AI 生成内容以原始素材为依据，如不同来源信息存在冲突，简报中会标注来源
- 建议定期人工审阅简报，确保信息准确性

## License

MIT
