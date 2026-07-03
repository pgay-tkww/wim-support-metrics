from __future__ import annotations

import base64
import json
from html import escape
from typing import Any
from urllib import error, request
from urllib.parse import urlencode


class ConfluenceClient:
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

    def find_child_page(
        self, space_key: str, parent_page_id: str, title: str
    ) -> dict[str, Any] | None:
        cql = (
            f'space = "{_escape_cql(space_key)}" '
            f'AND parent = "{_escape_cql(parent_page_id)}" '
            f'AND title = "{_escape_cql(title)}"'
        )
        data = self._request(
            "find child page",
            "get",
            "/rest/api/content/search",
            params={"cql": cql, "expand": "version", "limit": 1},
        )
        results = data.get("results", [])
        return results[0] if results else None

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._request(
            "get page",
            "get",
            f"/rest/api/content/{page_id}",
            params={"expand": "version"},
        )

    def create_page(
        self, space_key: str, parent_page_id: str, title: str, html: str
    ) -> dict[str, Any]:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": parent_page_id}],
            "body": _storage_body(html),
        }
        return self._request("create page", "post", "/rest/api/content", json=payload)

    def update_page(self, page_id: str, title: str, html: str) -> dict[str, Any]:
        page = self.get_page(page_id)
        current_version = page["version"]["number"]
        payload = {
            "type": page.get("type", "page"),
            "title": title,
            "version": {"number": current_version + 1},
            "body": _storage_body(html),
        }
        return self._request(
            "update page",
            "put",
            f"/rest/api/content/{page_id}",
            json=payload,
        )

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


def markdown_to_storage_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("### "):
            blocks.append(f"<h3>{escape(stripped[4:].strip())}</h3>")
            index += 1
            continue

        if stripped.startswith("## "):
            blocks.append(f"<h2>{escape(stripped[3:].strip())}</h2>")
            index += 1
            continue

        if stripped.startswith("# "):
            blocks.append(f"<h1>{escape(stripped[2:].strip())}</h1>")
            index += 1
            continue

        if stripped == "<details>":
            details_html, index = _details_block_to_html(lines, index)
            blocks.append(details_html)
            continue

        if stripped.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(_markdown_table_to_html(table_lines))
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:].strip())
                index += 1
            blocks.append(
                "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"
            )
            continue

        paragraph_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if (
                not candidate
                or candidate.startswith("# ")
                or candidate.startswith("## ")
                or candidate.startswith("### ")
                or candidate.startswith("|")
                or candidate.startswith("- ")
            ):
                break
            paragraph_lines.append(candidate)
            index += 1
        blocks.append(f"<p>{escape(' '.join(paragraph_lines))}</p>")

    return "".join(blocks)


def _storage_body(html: str) -> dict[str, Any]:
    return {
        "storage": {
            "value": html,
            "representation": "storage",
        }
    }


def _details_block_to_html(lines: list[str], start_index: int) -> tuple[str, int]:
    index = start_index + 1
    summary = ""
    inner_lines: list[str] = []

    if index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("<summary>") and stripped.endswith("</summary>"):
            summary = stripped.removeprefix("<summary>").removesuffix("</summary>")
            index += 1

    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "</details>":
            index += 1
            break
        inner_lines.append(lines[index])
        index += 1

    inner_html = markdown_to_storage_html("\n".join(inner_lines))
    return (
        '<ac:structured-macro ac:name="expand">'
        f'<ac:parameter ac:name="title">{escape(summary)}</ac:parameter>'
        f"<ac:rich-text-body>{inner_html}</ac:rich-text-body>"
        "</ac:structured-macro>",
        index,
    )


def _markdown_table_to_html(lines: list[str]) -> str:
    rows = [_split_table_row(line) for line in lines]
    if not rows:
        return ""

    header = rows[0]
    body_rows = rows[1:]
    if body_rows and _is_separator_row(body_rows[0]):
        body_rows = body_rows[1:]

    html = ["<table><thead><tr>"]
    html.extend(f"<th>{escape(cell)}</th>" for cell in header)
    html.append("</tr></thead><tbody>")
    for row in body_rows:
        html.append("<tr>")
        html.extend(f"<td>{_render_table_cell(cell)}</td>" for cell in row)
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_row(row: list[str]) -> bool:
    return all(cell and set(cell) <= {"-", ":", " "} for cell in row)


def _render_table_cell(cell: str) -> str:
    if cell.startswith("<details>") and cell.endswith("</details>"):
        return cell
    if "<a href=" in cell and "</a>" in cell:
        return cell
    return escape(cell)


def _escape_cql(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class _StdlibSession:
    def __init__(self) -> None:
        self.auth: tuple[str, str] | None = None

    def get(self, url: str, **kwargs: Any) -> "_StdlibResponse":
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> "_StdlibResponse":
        return self._request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> "_StdlibResponse":
        return self._request("PUT", url, **kwargs)

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
            token = base64.b64encode(f"{self.auth[0]}:{self.auth[1]}".encode("utf-8")).decode(
                "ascii"
            )
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
