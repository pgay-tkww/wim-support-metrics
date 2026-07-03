from __future__ import annotations

import base64
import json
from typing import Any
from urllib import error, request
from urllib.parse import urlencode


class JiraClient:
    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        session: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session or self._make_session()
        self._session.auth = (email, api_token)

    def search_issues(self, jql: str, fields: list[str]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        next_page_token: str | None = None
        max_results = 100

        while True:
            payload = {
                "jql": jql,
                "fields": fields,
                "fieldsByKeys": True,
                "maxResults": max_results,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            data = self._request("search issues", "post", "/rest/api/3/search/jql", json=payload)
            page_issues = data.get("issues", [])
            issues.extend(page_issues)

            if data.get("isLast", True):
                return issues

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                raise RuntimeError(
                    "Jira search did not return nextPageToken before the last page"
                )

            if not page_issues:
                raise RuntimeError(
                    "Jira search returned no issues before reaching the reported total"
                )

    def get_issue_changelog(self, issue_key: str) -> list[dict[str, Any]]:
        histories: list[dict[str, Any]] = []
        start_at = 0
        max_results = 100

        while True:
            data = self._request(
                "get issue changelog",
                "get",
                f"/rest/api/3/issue/{issue_key}/changelog",
                params={"startAt": start_at, "maxResults": max_results},
            )
            page_histories = data.get("values", [])
            histories.extend(page_histories)

            total = data.get("total", len(histories))
            if len(histories) >= total:
                return histories

            if not page_histories:
                raise RuntimeError(
                    "Jira changelog returned no values before reaching the reported total"
                )

            start_at += len(page_histories)

    def get_sprint(self, sprint_id: int) -> dict[str, Any]:
        return self._request("get sprint", "get", f"/rest/agile/1.0/sprint/{sprint_id}")

    def _request(self, operation: str, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = getattr(self._session, method)(url, **kwargs)

        if not getattr(response, "ok", 200 <= getattr(response, "status_code", 0) < 300):
            raise RuntimeError(
                f"{operation} failed with status code {getattr(response, 'status_code', 'unknown')}"
            )

        return response.json()

    def _make_session(self) -> Any:
        return _StdlibSession()


class _StdlibSession:
    def __init__(self) -> None:
        self.auth: tuple[str, str] | None = None

    def get(self, url: str, **kwargs: Any) -> "_StdlibResponse":
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> "_StdlibResponse":
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs: Any) -> "_StdlibResponse":
        body = kwargs.get("json")
        params = kwargs.get("params")
        if params:
            query = urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.auth is not None:
            token = base64.b64encode(f"{self.auth[0]}:{self.auth[1]}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")

        try:
            with request.urlopen(req) as response:
                return _StdlibResponse(response.read(), response.status)
        except error.HTTPError as exc:
            return _StdlibResponse(exc.read(), exc.code)


class _StdlibResponse:
    def __init__(self, body: bytes, status_code: int) -> None:
        self._body = body
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict[str, Any]:
        if not self._body:
            return {}
        return json.loads(self._body.decode("utf-8"))
