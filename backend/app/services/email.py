import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

from app.config import get_settings


class EmailNotConfigured(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


def is_configured() -> bool:
    return get_settings().email_configured


def _site_url(path: str, token: str) -> str:
    settings = get_settings()
    return (
        f"{settings.public_base_url}{settings.public_base_path}"
        f"{path}?token={quote(token)}"
    )


def build_verification_url(token: str) -> str:
    return _site_url("/verify-email", token)


def build_password_reset_url(token: str) -> str:
    return _site_url("/reset-password", token)


def send_email(*, to: str, subject: str, text: str, html: str) -> None:
    settings = get_settings()
    if not settings.email_configured:
        raise EmailNotConfigured("邮件服务未配置")

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout,
        ) as smtp:
            smtp.ehlo()
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError, TimeoutError) as error:
        raise EmailDeliveryError("邮件发送失败") from error


def _wrap_html(title: str, intro: str, url: str, button: str) -> str:
    return f"""\
<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;padding:32px;background:#f7f4ff;color:#211b33;
               font-family:Segoe UI,PingFang SC,Microsoft YaHei,sans-serif;">
    <div style="max-width:560px;margin:0 auto;padding:32px;background:#fff;
                border:1px solid #e7e1f7;border-radius:20px;">
      <p style="margin:0 0 10px;color:#7357ff;font-size:12px;letter-spacing:.16em;">
        C / STUDY NOTES
      </p>
      <h1 style="margin:0 0 16px;font-size:24px;">{title}</h1>
      <p style="margin:0 0 24px;color:#756e8a;line-height:1.8;">{intro}</p>
      <p style="margin:0 0 24px;">
        <a href="{url}"
           style="display:inline-block;padding:12px 20px;border-radius:999px;
                  background:#7357ff;color:#fff;text-decoration:none;font-weight:600;">
          {button}
        </a>
      </p>
      <p style="margin:0;color:#938ba8;font-size:12px;line-height:1.7;">
        链接只允许本站地址。若非本人操作，请忽略此邮件。
      </p>
    </div>
  </body>
</html>
"""


def send_verification_email(to: str, token: str) -> None:
    settings = get_settings()
    url = build_verification_url(token)
    send_email(
        to=to,
        subject=f"{settings.site_title}：验证邮箱",
        text=f"请在浏览器打开以下本站链接完成邮箱验证：\n{url}\n",
        html=_wrap_html(
            "验证你的邮箱",
            "完成验证后即可登录并开始整理自己的 C 语言笔记。",
            url,
            "验证邮箱",
        ),
    )


def send_password_reset_email(to: str, token: str) -> None:
    settings = get_settings()
    url = build_password_reset_url(token)
    send_email(
        to=to,
        subject=f"{settings.site_title}：重置密码",
        text=f"请在浏览器打开以下本站链接重置密码：\n{url}\n",
        html=_wrap_html(
            "重置密码",
            "此链接一次性有效。重置后，该账号的所有旧会话都会失效。",
            url,
            "重置密码",
        ),
    )
