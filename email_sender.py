"""
email_sender.py - 邮件推送模块
通过 SMTP 发送 Markdown 简报邮件，附带 .md 附件
所有密钥从环境变量读取
"""

import os
import smtplib
import yaml
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def send_report(report_md: str, report_filename: str, config: dict = None) -> bool:
    """
    通过 SMTP 发送简报邮件

    参数:
        report_md:       Markdown 简报正文
        report_filename: 附件文件名（如 briefing_2025-01-01.md）
        config:          配置字典，可选

    返回:
        bool: 发送成功返回 True
    """
    if config is None:
        config = load_config()

    email_cfg = config.get("email", {})

    # ── 从环境变量读取邮件配置 ──
    smtp_host = os.environ.get(email_cfg.get("smtp_host_env", "SMTP_HOST"), "")
    smtp_port = int(os.environ.get(email_cfg.get("smtp_port_env", "SMTP_PORT"), "587"))
    smtp_user = os.environ.get(email_cfg.get("smtp_user_env", "SMTP_USER"), "")
    smtp_pass = os.environ.get(email_cfg.get("smtp_pass_env", "SMTP_PASS"), "")
    sender    = os.environ.get(email_cfg.get("sender_env", "EMAIL_SENDER"), "")
    recipients_str = os.environ.get(email_cfg.get("recipients_env", "EMAIL_RECIPIENTS"), "")

    # 校验必填项
    if not all([smtp_host, smtp_user, smtp_pass, sender, recipients_str]):
        missing = []
        if not smtp_host:  missing.append("SMTP_HOST")
        if not smtp_user:  missing.append("SMTP_USER")
        if not smtp_pass:  missing.append("SMTP_PASS")
        if not sender:     missing.append("EMAIL_SENDER")
        if not recipients_str: missing.append("EMAIL_RECIPIENTS")
        print(f"[Email] 配置缺失，跳过发送: {', '.join(missing)}")
        return False

    # 解析收件人列表（逗号分隔）
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    if not recipients:
        print("[Email] 收件人列表为空，跳过发送")
        return False

    # ── 构建邮件 ──
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"🚢 美国航母每日动态简报 - {today}"

    msg = MIMEMultipart("mixed")
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject

    # 邮件正文：先放纯文本 Markdown，再放 HTML 版本（兼容不同客户端）
    text_part = MIMEText(report_md, "plain", "utf-8")
    msg.attach(text_part)

    # HTML 版本（简单的 Markdown → HTML 转换）
    html_body = _md_to_simple_html(report_md)
    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    # 附件：.md 文件内容
    attachment = MIMEBase("application", "octet-stream")
    attachment.set_payload(report_md.encode("utf-8"))
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f"attachment; filename=\"{report_filename}\""
    )
    msg.attach(attachment)

    # ── 发送 ──
    try:
        # 根据端口选择加密方式
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()
        print(f"[Email] ✅ 简报已发送至 {len(recipients)} 个收件人")
        return True

    except Exception as e:
        print(f"[Email] ❌ 发送失败: {e}")
        return False


def _md_to_simple_html(md_text: str) -> str:
    """
    极简 Markdown → HTML 转换（仅处理标题、粗体、列表、分割线）
    不依赖第三方库，够用即可
    """
    lines = md_text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # 标题
        if stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        # 分割线
        elif stripped in ("---", "***", "___"):
            html_lines.append("<hr>")
        # 列表项
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = stripped[2:]
            # 粗体
            content = content.replace("**", "<strong>", 1)
            if "<strong>" in content and "</strong>" not in content:
                content = content.replace("<strong>", "<strong>", 0)  # no-op safety
            html_lines.append(f"<li>{content}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if stripped.startswith("> "):
                html_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
            elif stripped:
                html_lines.append(f"<p>{stripped}</p>")

    if in_list:
        html_lines.append("</ul>")

    body = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>航母简报</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px;}} h1{{color:#1a365d;}} h2{{color:#2c5282;}} blockquote{{color:#666;border-left:3px solid #ccc;padding-left:12px;}}</style>
</head>
<body>
{body}
</body>
</html>"""


# 独立运行时测试
if __name__ == "__main__":
    test_md = "# 测试简报\n> 这是一封测试邮件\n\n- 项目1\n- 项目2\n\n---\n*测试完成*"
    send_report(test_md, "test_briefing.md")
