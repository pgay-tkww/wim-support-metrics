from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    jira_sprint_field: str
    confluence_base_url: str
    confluence_email: str
    confluence_api_token: str
    confluence_space_key: str
    confluence_parent_page_id: str


def _read_env(name: str, *, required: bool, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default if not required else None

    stripped = value.strip()
    if not stripped:
        return default if not required else None

    return stripped


def _read_required_env(name: str) -> str | None:
    return _read_env(name, required=True)


def _read_optional_env(name: str, default: str) -> str:
    value = _read_env(name, required=False, default=default)
    assert value is not None
    return value


def load_config() -> AppConfig:
    required = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "CONFLUENCE_BASE_URL",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
    ]
    missing = [key for key in required if _read_required_env(key) is None]
    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))

    jira_base_url = _read_required_env("JIRA_BASE_URL").rstrip("/")
    jira_email = _read_required_env("JIRA_EMAIL")
    jira_api_token = _read_required_env("JIRA_API_TOKEN")
    confluence_base_url = _read_required_env("CONFLUENCE_BASE_URL").rstrip("/")
    confluence_email = _read_required_env("CONFLUENCE_EMAIL")
    confluence_api_token = _read_required_env("CONFLUENCE_API_TOKEN")

    return AppConfig(
        jira_base_url=jira_base_url,
        jira_email=jira_email,
        jira_api_token=jira_api_token,
        jira_sprint_field=_read_optional_env("JIRA_SPRINT_FIELD", "customfield_10261"),
        confluence_base_url=confluence_base_url,
        confluence_email=confluence_email,
        confluence_api_token=confluence_api_token,
        confluence_space_key=_read_optional_env("CONFLUENCE_SPACE_KEY", "WWIM"),
        confluence_parent_page_id=_read_optional_env("CONFLUENCE_PARENT_PAGE_ID", "6499926021"),
    )
