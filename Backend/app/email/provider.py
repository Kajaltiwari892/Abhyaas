import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as StandardEmailMessage
from email.utils import formataddr
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger("abhyaas.email")


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text: str


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailProvider:
    """Development provider that sends nothing externally and logs the email body."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "\n--- ABHYAAS DEVELOPMENT EMAIL ---\nTo: %s\nSubject: %s\n\n%s\n"
            "--- END DEVELOPMENT EMAIL ---",
            message.recipient,
            message.subject,
            message.text,
        )


class SmtpEmailProvider:
    """Send transactional mail through an authenticated TLS/SSL SMTP account."""

    def __init__(self) -> None:
        settings = get_settings()
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        # Google displays app passwords in four groups for readability, while
        # Gmail SMTP expects the underlying 16-character credential.
        if self.host.casefold() == "smtp.gmail.com":
            self.password = "".join(self.password.split())
        self.use_ssl = settings.smtp_use_ssl
        self.sender = settings.email_from_address or settings.smtp_username
        self.sender_name = settings.email_from_name
        if not all((self.host, self.username, self.password, self.sender)):
            raise RuntimeError("SMTP email is selected but its credentials are incomplete")

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        outgoing = StandardEmailMessage()
        outgoing["From"] = formataddr((self.sender_name, self.sender))
        outgoing["To"] = message.recipient
        outgoing["Subject"] = message.subject
        outgoing.set_content(message.text)

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as client:
                client.login(self.username, self.password)
                client.send_message(outgoing)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=20) as client:
                client.ehlo()
                client.starttls()
                client.ehlo()
                client.login(self.username, self.password)
                client.send_message(outgoing)
        logger.info("Transactional email sent to %s", message.recipient)


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.email_provider == "smtp":
        return SmtpEmailProvider()
    if settings.email_provider == "console" and settings.app_env != "production":
        return ConsoleEmailProvider()
    raise RuntimeError(f"Email provider '{settings.email_provider}' is not configured")
