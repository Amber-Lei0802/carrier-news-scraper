# 🚢 美国航母每日动态简报（US Carrier Daily Briefing）

自动抓取公开新闻 → 大模型分析生成简报 → SMTP 邮件推送

**技术栈：** Python · GitHub Actions（免费）· Gemini Flash / OpenAI · SMTP

---

## 项目结构

```
us-carrier-briefing/
├── .github/
│   └── workflows/
│       └── crawl.yml              # GitHub Actions 定时工作流
├── output/                        # 生成的报告存放目录（自动创建）
├── main.py                        # 主入口：抓取 → AI → 保存 → 邮件
├── scraper.py                     # 新闻抓取模块（RSS + HTML）
├── ai_client.py                   # 大模型调用（Gemini / OpenAI）
├── email_sender.py                # SMTP 邮件推送
├── config.yaml                    # 配置文件（源、模型、邮件等）
├── requirements.txt               # Python 依赖
├── .env.example                   # 环境变量示例
├── .gitignore
└── README.md
```

---

## 快速部署（5 分钟）

### 1. 创建 GitHub 仓库

```bash
git init
git add .
git commit -m "init: US Carrier Daily Briefing"
git branch -M main
git remote add origin https://github.com/你的用户名/us-carrier-briefing.git
git push -u origin main
```

### 2. 获取 Gemini API Key（免费）

1. 访问 [Google AI Studio](https://aistudio.google.com/apikey)
2. 点击 **Create API Key**
3. 复制密钥

> 免费额度：Gemini 2.5 Flash 10 RPM / 500 RPD，完全够用

### 3. 配置 GitHub Actions Secrets

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 名称 | 值 | 说明 |
|---|---|---|
| `GEMINI_API_KEY` | `AIza...` | Gemini API 密钥 |
| `SMTP_HOST` | `smtp.qq.com` | SMTP 服务器地址 |
| `SMTP_PORT` | `465` | SMTP 端口（SSL=465, TLS=587）|
| `SMTP_USER` | `your@qq.com` | SMTP 登录用户名 |
| `SMTP_PASS` | `xxxx xxxx` | SMTP 授权码（非登录密码）|
| `EMAIL_SENDER` | `your@qq.com` | 发件人地址 |
| `EMAIL_RECIPIENTS` | `a@x.com,b@x.com` | 收件人，逗号分隔 |

> 如使用 OpenAI，添加 `OPENAI_API_KEY` 和可选的 `OPENAI_BASE_URL`

### 4. 配置邮箱 SMTP

**QQ 邮箱：**
1. 登录 QQ 邮箱 → 设置 → 账户
2. 开启 **IMAP/SMTP 服务**
3. 生成授权码 → 填入 `SMTP_PASS`

**Gmail：**
1. 开启两步验证
2. 生成 App Password → 填入 `SMTP_PASS`

### 5. 完成

推送代码后，GitHub Actions 每天 UTC 06:00（北京时间 14:00）自动运行。
也可在 Actions 页面手动触发。

---

## 修改运行时间

编辑 `.github/workflows/crawl.yml`：

```yaml
# 每天 UTC 06:00（北京时间 14:00）
- cron: "0 6 * * *"

# 改为每天早上 8:00 北京时间：
- cron: "0 0 * * *"

# 改为每 12 小时运行一次：
- cron: "0 0,12 * * *"
```

---

## 自定义新闻源

编辑 `config.yaml` 中的 `news_sources`，支持添加更多 RSS 或 HTML 源：

```yaml
news_sources:
  rss:
    - name: "自定义源"
      url: "https://example.com/rss"
  html:
    - name: "网页抓取"
      url: "https://example.com/news"
      article_selector: "article"
      title_selector: "h3"
      link_selector: "a"
```

---

## 切换大模型

编辑 `config.yaml`：

```yaml
ai:
  provider: "openai"      # gemini 或 openai
  openai:
    model: "gpt-4o-mini"
```

---

## 常见问题

**Q: 报告文件在哪里？**  
A: 每次运行后自动提交到仓库的 `output/` 目录。

**Q: 邮件发送失败？**  
A: 检查 Secrets 是否正确，SMTP 授权码是否为专用授权码（非登录密码）。

**Q: Gemini 限流怎么办？**  
A: 已内置模型自动降级，`2.5-flash → 2.0-flash → 2.0-flash-lite`，无需手动处理。

**Q: 如何添加中文新闻源？**  
A: 在 `config.yaml` 的 RSS 列表中添加中文 RSS 地址即可。
