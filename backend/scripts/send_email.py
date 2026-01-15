#!/usr/bin/env python3
import argparse
import os
import smtplib
from pathlib import Path
from dotenv import load_dotenv
from email.message import EmailMessage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a test email via SMTP.")
    parser.add_argument(
        "--to",
        default="system5@mail.ru",
        help="Recipient email address.",
    )
    parser.add_argument(
        "--subject",
        default="Подтверждение оплаты",
        help="Email subject.",
    )
    parser.add_argument(
        "--message",
        default="Тестовое сообщение.",
        help="Email message body.",
    )
    return parser.parse_args()


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def main() -> int:
    args = parse_args()

    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    host = get_env("EMAIL_HOST")
    port_raw = get_env("EMAIL_PORT", "587")
    user = get_env("EMAIL_HOST_USER")
    password = get_env("EMAIL_HOST_PASSWORD")
    use_tls = get_env("EMAIL_USE_TLS", "True").lower() == "true"
    use_ssl = get_env("EMAIL_USE_SSL", "False").lower() == "true"
    sender = get_env("DEFAULT_FROM_EMAIL", "support@fibonatty.ru")

    if not host or not user or not password:
        raise SystemExit(
            "Missing SMTP settings. Set EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD."
        )

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid EMAIL_PORT value: {port_raw}") from exc

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg.set_content(args.message)

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)

    try:
        if use_tls and not use_ssl:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)
    finally:
        server.quit()

    print(f"Email sent to {args.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
