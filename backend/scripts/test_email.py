"""Send a delivery test through the configured SMTP service.

Usage:
    python scripts/test_email.py recipient@example.com

This sends a plain test message without tokens or links. Use it to verify the
production SMTP credentials and inbox delivery before inviting users.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.email import EmailDeliveryError, EmailNotConfigured, send_email


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipient")
    args = parser.parse_args()
    settings = get_settings()

    if not settings.email_configured:
        raise SystemExit(
            "邮件服务未配置：请设置 SMTP_HOST、SMTP_FROM 等服务端环境变量"
        )

    try:
        send_email(
            to=args.recipient,
            subject=f"{settings.site_title}：邮件发送测试",
            text="这是一封配置测试邮件，不包含任何验证链接。\n",
            html=(
                "<p>这是一封配置测试邮件，不包含任何验证链接。</p>"
                f"<p>站点：{settings.site_title}</p>"
            ),
        )
    except (EmailNotConfigured, EmailDeliveryError) as error:
        raise SystemExit(f"邮件发送失败：{error}") from error

    print(f"test email sent to {args.recipient}")


if __name__ == "__main__":
    main()
