import pytest

from wim_metrics.config import ConfigError, load_config


def test_load_config_requires_env(monkeypatch):
    for key in [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "CONFLUENCE_BASE_URL",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(
        ConfigError,
        match=(
            "Missing required environment variables: "
            "JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, "
            "CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN"
        ),
    ) as excinfo:
        load_config()

    assert (
        str(excinfo.value)
        == "Missing required environment variables: "
        "JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, "
        "CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN"
    )


def test_load_config_rejects_whitespace_only_required_values(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "   ")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://theknotww.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "conf-token")

    with pytest.raises(ConfigError, match="Missing required environment variables: JIRA_BASE_URL"):
        load_config()


def test_load_config_strips_trailing_slashes_from_base_urls(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", " https://theknotww.atlassian.net/ ")
    monkeypatch.setenv("JIRA_EMAIL", " user@example.com ")
    monkeypatch.setenv("JIRA_API_TOKEN", " jira-token ")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", " https://theknotww.atlassian.net/wiki/ ")
    monkeypatch.setenv("CONFLUENCE_EMAIL", " user@example.com ")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", " conf-token ")

    config = load_config()

    assert config.jira_base_url == "https://theknotww.atlassian.net"
    assert config.confluence_base_url == "https://theknotww.atlassian.net/wiki"
    assert config.jira_email == "user@example.com"
    assert config.jira_api_token == "jira-token"
    assert config.confluence_email == "user@example.com"
    assert config.confluence_api_token == "conf-token"


def test_blank_optional_confluence_settings_use_defaults(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://theknotww.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://theknotww.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "conf-token")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "   ")
    monkeypatch.setenv("CONFLUENCE_PARENT_PAGE_ID", "   ")

    config = load_config()

    assert config.confluence_space_key == "WWIM"
    assert config.confluence_parent_page_id == "6499926021"


def test_load_config_defaults_confluence_page_settings(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://theknotww.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://theknotww.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "conf-token")

    config = load_config()

    assert config.confluence_space_key == "WWIM"
    assert config.confluence_parent_page_id == "6499926021"
    assert config.jira_sprint_field == "customfield_10261"


def test_load_config_allows_jira_sprint_field_override(monkeypatch):
    monkeypatch.setenv("JIRA_BASE_URL", "https://theknotww.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://theknotww.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "user@example.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "conf-token")
    monkeypatch.setenv("JIRA_SPRINT_FIELD", "customfield_12345")

    config = load_config()

    assert config.jira_sprint_field == "customfield_12345"
