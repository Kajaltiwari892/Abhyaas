from types import SimpleNamespace

import pytest

from app.email import provider


class FakeSmtpClient:
    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.connection = (host, port, timeout)
        self.login_credentials: tuple[str, str] | None = None
        self.message = None

    def __enter__(self) -> "FakeSmtpClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.login_credentials = (username, password)

    def send_message(self, message: object) -> None:
        self.message = message


def smtp_settings(**overrides: object) -> SimpleNamespace:
    values = {
        "app_env": "production",
        "email_provider": "smtp",
        "email_from_address": "sender@example.com",
        "email_from_name": "Abhyaas",
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_username": "sender@example.com",
        "smtp_password": "app-password",
        "smtp_use_ssl": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_smtp_provider_sends_transactional_email(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeSmtpClient("", 0, 0)
    monkeypatch.setattr(provider, "get_settings", lambda: smtp_settings())
    monkeypatch.setattr(
        provider.smtplib,
        "SMTP_SSL",
        lambda host, port, timeout: (
            setattr(fake_client, "connection", (host, port, timeout)) or fake_client
        ),
    )

    email_provider = provider.get_email_provider()
    await email_provider.send(
        provider.EmailMessage(
            recipient="student@example.com",
            subject="Reset your Abhyaas password",
            text="Open the secure reset link.",
        )
    )

    assert fake_client.connection == ("smtp.example.com", 465, 20)
    assert fake_client.login_credentials == ("sender@example.com", "app-password")
    assert fake_client.message["To"] == "student@example.com"
    assert fake_client.message["From"] == "Abhyaas <sender@example.com>"


def test_console_provider_cannot_silently_run_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider,
        "get_settings",
        lambda: smtp_settings(email_provider="console"),
    )
    with pytest.raises(RuntimeError, match="not configured"):
        provider.get_email_provider()
