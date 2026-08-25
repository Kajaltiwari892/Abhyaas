import logging
from dataclasses import dataclass
from typing import Protocol

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


def get_email_provider() -> EmailProvider:
    return ConsoleEmailProvider()
