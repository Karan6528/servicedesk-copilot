"""Settings, read from environment variables (12-factor style).

Everything has a safe default so the app runs with zero configuration.
Integrations switch on only when their variables are set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    app_name: str = "ServiceDesk Copilot"
    environment: str = field(default_factory=lambda: _env("APP_ENV", "local"))
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./servicedesk.db"))

    # Optional LLM. Without a key the local rule-based engine is used.
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    # Azure OpenAI (optional): set endpoint + deployment + key
    azure_openai_endpoint: str = field(default_factory=lambda: _env("AZURE_OPENAI_ENDPOINT"))
    azure_openai_deployment: str = field(default_factory=lambda: _env("AZURE_OPENAI_DEPLOYMENT"))
    azure_openai_key: str = field(default_factory=lambda: _env("AZURE_OPENAI_KEY"))
    azure_openai_api_version: str = field(default_factory=lambda: _env("AZURE_OPENAI_API_VERSION", "2024-06-01"))

    # Power Automate: HTTP-trigger URL of your flow ("When an HTTP request is received")
    power_automate_webhook_url: str = field(default_factory=lambda: _env("POWER_AUTOMATE_WEBHOOK_URL"))

    # ServiceNow Personal Developer Instance, e.g. dev12345.service-now.com
    servicenow_instance: str = field(default_factory=lambda: _env("SERVICENOW_INSTANCE"))
    servicenow_user: str = field(default_factory=lambda: _env("SERVICENOW_USER"))
    servicenow_password: str = field(default_factory=lambda: _env("SERVICENOW_PASSWORD"))

    # Which urgencies trigger the integrations
    escalate_urgencies: tuple[str, ...] = ("critical", "high")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key) or bool(
            self.azure_openai_endpoint and self.azure_openai_deployment and self.azure_openai_key
        )

    @property
    def servicenow_enabled(self) -> bool:
        return bool(self.servicenow_instance and self.servicenow_user and self.servicenow_password)

    @property
    def power_automate_enabled(self) -> bool:
        return bool(self.power_automate_webhook_url)


def get_settings() -> Settings:
    return Settings()
