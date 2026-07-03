from wim_metrics.confluence_client import ConfluenceClient, markdown_to_storage_html


class FakeResponse:
    def __init__(self, json_data, status_code=200, ok=True):
        self._json_data = json_data
        self.status_code = status_code
        self.ok = ok

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None, put_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.put_responses = list(put_responses or [])
        self.get_calls = []
        self.post_calls = []
        self.put_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.post_responses.pop(0)

    def put(self, url, **kwargs):
        self.put_calls.append((url, kwargs))
        return self.put_responses.pop(0)


def make_client(session):
    return ConfluenceClient(
        base_url="https://theknotww.atlassian.net/wiki",
        email="user@example.com",
        api_token="confluence-token",
        session=session,
    )


def test_find_child_page_by_title_queries_parent_and_space():
    session = FakeSession(
        get_responses=[
            FakeResponse(
                {
                    "results": [
                        {
                            "id": "123456",
                            "title": "WIM Support Metrics - 2026-06-29",
                            "version": {"number": 7},
                        }
                    ]
                }
            )
        ]
    )
    client = make_client(session)

    page = client.find_child_page(
        "WWIM", "6499926021", "WIM Support Metrics - 2026-06-29"
    )

    assert page == {
        "id": "123456",
        "title": "WIM Support Metrics - 2026-06-29",
        "version": {"number": 7},
    }
    assert session.get_calls == [
        (
            "https://theknotww.atlassian.net/wiki/rest/api/content/search",
            {
                "params": {
                    "cql": (
                        'space = "WWIM" AND parent = "6499926021" '
                        'AND title = "WIM Support Metrics - 2026-06-29"'
                    ),
                    "expand": "version",
                    "limit": 1,
                }
            },
        )
    ]


def test_create_weekly_page_posts_child_under_parent():
    session = FakeSession(post_responses=[FakeResponse({"id": "123456"})])
    client = make_client(session)

    page = client.create_page(
        "WWIM",
        "6499926021",
        "WIM Support Metrics - 2026-06-29",
        "<h1>Weekly Metrics</h1>",
    )

    assert page == {"id": "123456"}
    assert session.post_calls == [
        (
            "https://theknotww.atlassian.net/wiki/rest/api/content",
            {
                "json": {
                    "type": "page",
                    "title": "WIM Support Metrics - 2026-06-29",
                    "space": {"key": "WWIM"},
                    "ancestors": [{"id": "6499926021"}],
                    "body": {
                        "storage": {
                            "value": "<h1>Weekly Metrics</h1>",
                            "representation": "storage",
                        }
                    },
                }
            },
        )
    ]


def test_update_parent_page_increments_version():
    session = FakeSession(
        get_responses=[
            FakeResponse(
                {
                    "id": "6499926021",
                    "type": "page",
                    "title": "WIM Support Metrics",
                    "version": {"number": 3},
                }
            )
        ],
        put_responses=[FakeResponse({"id": "6499926021", "version": {"number": 4}})],
    )
    client = make_client(session)

    page = client.update_page(
        "6499926021", "WIM Support Metrics", "<p>Updated index</p>"
    )

    assert page == {"id": "6499926021", "version": {"number": 4}}
    assert session.get_calls == [
        (
            "https://theknotww.atlassian.net/wiki/rest/api/content/6499926021",
            {"params": {"expand": "version"}},
        )
    ]
    assert session.put_calls == [
        (
            "https://theknotww.atlassian.net/wiki/rest/api/content/6499926021",
            {
                "json": {
                    "type": "page",
                    "title": "WIM Support Metrics",
                    "version": {"number": 4},
                    "body": {
                        "storage": {
                            "value": "<p>Updated index</p>",
                            "representation": "storage",
                        }
                    },
                }
            },
        )
    ]


def test_markdown_to_storage_html_supports_generated_subset():
    markdown = """# Weekly Metrics

Plain intro.

## Tickets
| Status | Count |
| --- | ---: |
| Done | 4 |

- First item
- Second item
"""

    assert markdown_to_storage_html(markdown) == (
        "<h1>Weekly Metrics</h1>"
        "<p>Plain intro.</p>"
        "<h2>Tickets</h2>"
        "<table><thead><tr><th>Status</th><th>Count</th></tr></thead>"
        "<tbody><tr><td>Done</td><td>4</td></tr></tbody></table>"
        "<ul><li>First item</li><li>Second item</li></ul>"
    )


def test_markdown_to_storage_html_preserves_links_in_table_cells():
    markdown = """| Metric | Count | Issues |
| --- | ---: | --- |
| Support Queue | 1 | <a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">1 issue</a> |
"""

    assert markdown_to_storage_html(markdown) == (
        "<table><thead><tr><th>Metric</th><th>Count</th><th>Issues</th></tr></thead>"
        "<tbody><tr><td>Support Queue</td><td>1</td>"
        '<td><a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">1 issue</a></td>'
        "</tr></tbody></table>"
    )


def test_markdown_to_storage_html_preserves_links_inside_count_cells():
    markdown = """| Metric | Count |
| --- | ---: |
| General Queue | 270 (<a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>) |
"""

    assert markdown_to_storage_html(markdown) == (
        "<table><thead><tr><th>Metric</th><th>Count</th></tr></thead>"
        '<tbody><tr><td>General Queue</td><td>270 (<a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>)</td>'
        "</tr></tbody></table>"
    )


def test_markdown_to_storage_html_renders_details_as_confluence_expand_macro():
    markdown = """<details>
<summary>Phoenix</summary>

### Summary

| Metric | Phoenix | Total |
| --- | ---: | ---: |
| Squad Queue | 5 (<a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>) | 10 (50%) |
</details>
"""

    html = markdown_to_storage_html(markdown)

    assert html == (
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">Phoenix</ac:parameter>'
        "<ac:rich-text-body>"
        "<h3>Summary</h3>"
        "<table><thead><tr><th>Metric</th><th>Phoenix</th><th>Total</th></tr></thead>"
        '<tbody><tr><td>Squad Queue</td><td>5 (<a href="https://example.com/issues/?jql=key%20in%20%28GPWIM-123%29">query</a>)</td><td>10 (50%)</td></tr></tbody></table>'
        "</ac:rich-text-body>"
        "</ac:structured-macro>"
    )
