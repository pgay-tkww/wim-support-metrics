from wim_metrics.jira_client import JiraClient


class FakeResponse:
    def __init__(self, json_data, status_code=200, ok=True):
        self._json_data = json_data
        self.status_code = status_code
        self.ok = ok

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.post_responses.pop(0)


def test_search_issues_posts_jql_and_paginates():
    session = FakeSession(
        post_responses=[
            FakeResponse(
                {
                    "issues": [{"key": "GPWIM-1"}],
                    "isLast": False,
                    "nextPageToken": "next-token",
                }
            ),
            FakeResponse({"issues": [{"key": "GPWIM-2"}], "isLast": True}),
        ]
    )
    client = JiraClient(
        base_url="https://theknotww.atlassian.net",
        email="user@example.com",
        api_token="jira-token",
        session=session,
    )

    issues = client.search_issues("project = GPWIM AND component in (Support)", ["summary"])

    assert issues == [{"key": "GPWIM-1"}, {"key": "GPWIM-2"}]
    assert len(session.post_calls) == 2
    first_call = session.post_calls[0]
    assert first_call[0] == "https://theknotww.atlassian.net/rest/api/3/search/jql"
    assert first_call[1]["json"]["jql"] == "project = GPWIM AND component in (Support)"
    assert first_call[1]["json"]["fields"] == ["summary"]
    assert first_call[1]["json"]["fieldsByKeys"] is True
    assert first_call[1]["json"]["maxResults"] == 100
    assert "nextPageToken" not in first_call[1]["json"]
    second_call = session.post_calls[1]
    assert second_call[1]["json"]["nextPageToken"] == "next-token"


def test_base_url_is_exposed_as_public_contract():
    client = JiraClient(
        base_url="https://theknotww.atlassian.net/",
        email="user@example.com",
        api_token="jira-token",
        session=FakeSession(),
    )

    assert client.base_url == "https://theknotww.atlassian.net"


def test_get_issue_changelog_calls_paginated_endpoint():
    session = FakeSession(
        get_responses=[
            FakeResponse(
                {
                    "startAt": 0,
                    "maxResults": 100,
                    "total": 2,
                    "values": [{"created": "2026-06-01T09:00:00+02:00", "items": []}],
                }
            ),
            FakeResponse(
                {
                    "startAt": 1,
                    "maxResults": 100,
                    "total": 2,
                    "values": [{"created": "2026-06-02T09:00:00+02:00", "items": []}],
                }
            ),
        ]
    )
    client = JiraClient(
        base_url="https://theknotww.atlassian.net",
        email="user@example.com",
        api_token="jira-token",
        session=session,
    )

    histories = client.get_issue_changelog("GPWIM-123")

    assert histories == [
        {"created": "2026-06-01T09:00:00+02:00", "items": []},
        {"created": "2026-06-02T09:00:00+02:00", "items": []},
    ]
    assert session.get_calls == [
        (
            "https://theknotww.atlassian.net/rest/api/3/issue/GPWIM-123/changelog",
            {"params": {"startAt": 0, "maxResults": 100}},
        ),
        (
            "https://theknotww.atlassian.net/rest/api/3/issue/GPWIM-123/changelog",
            {"params": {"startAt": 1, "maxResults": 100}},
        ),
    ]


def test_get_issue_changelog_raises_on_empty_page_before_total():
    session = FakeSession(
        get_responses=[
            FakeResponse(
                {
                    "startAt": 0,
                    "maxResults": 100,
                    "total": 2,
                    "values": [{"created": "2026-06-01T09:00:00+02:00", "items": []}],
                }
            ),
            FakeResponse(
                {
                    "startAt": 1,
                    "maxResults": 100,
                    "total": 2,
                    "values": [],
                }
            ),
        ]
    )
    client = JiraClient(
        base_url="https://theknotww.atlassian.net",
        email="user@example.com",
        api_token="jira-token",
        session=session,
    )

    try:
        client.get_issue_changelog("GPWIM-123")
    except RuntimeError as exc:
        assert str(exc) == "Jira changelog returned no values before reaching the reported total"
    else:
        raise AssertionError("Expected RuntimeError for empty changelog page")


def test_get_sprint_returns_metadata():
    session = FakeSession(
        get_responses=[
            FakeResponse(
                {
                    "id": 123,
                    "name": "WIM Sprint 42",
                    "state": "active",
                    "startDate": "2026-06-15T09:00:00+02:00",
                    "endDate": "2026-06-29T09:00:00+02:00",
                }
            )
        ]
    )
    client = JiraClient(
        base_url="https://theknotww.atlassian.net",
        email="user@example.com",
        api_token="jira-token",
        session=session,
    )

    sprint = client.get_sprint(123)

    assert sprint == {
        "id": 123,
        "name": "WIM Sprint 42",
        "state": "active",
        "startDate": "2026-06-15T09:00:00+02:00",
        "endDate": "2026-06-29T09:00:00+02:00",
    }
    assert session.get_calls == [
        ("https://theknotww.atlassian.net/rest/agile/1.0/sprint/123", {})
    ]
