"""
Email 推送模块 —— 发送 HTML 格式的每日双拼日报
支持 Gmail SMTP 和其他 SMTP 服务（如 Resend）
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def send_daily_email(
    html_content: str,
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: Optional[str] = None,
) -> bool:
    """发送 HTML 日报邮件"""
    if not all([smtp_server, sender_email, sender_password, recipient_email]):
        logger.error("邮件配置不完整，跳过发送")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    if subject is None:
        subject = f"📬 每日双拼日报 | AI快讯 × 古代故事 | {today}"

    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # 添加 HTML 正文
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        # Gmail 使用 STARTTLS
        if "gmail" in smtp_server.lower():
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
        else:
            # 其他 SMTP 服务
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())

        logger.info(f"✓ 邮件已发送 → {recipient_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("✗ 邮件认证失败：请检查 Gmail 应用专用密码（不是登录密码）")
        logger.error("  参考：https://support.google.com/accounts/answer/185833")
        return False
    except Exception as e:
        logger.error(f"✗ 邮件发送失败: {e}")
        return False
