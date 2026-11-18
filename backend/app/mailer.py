"""Sending email (password-reset links). Optional: without SMTP settings nothing is sent and the caller says so."""
import logging
import smtplib
from email.message import EmailMessage

from app import config

log = logging.getLogger("mindtrace.mail")


def enabled() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_FROM and config.PUBLIC_URL)


def send(to: str, subject: str, body: str) -> bool:  # tests replace this
    if not enabled():
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("reset email to a user failed: %s", type(exc).__name__)  # never log the address or link
        return False
