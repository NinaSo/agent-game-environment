"""Local HTTP boundary tests; never use model inference."""

from io import BytesIO
from types import SimpleNamespace

import pytest

import serve


@pytest.fixture
def dashboard_server(tmp_path, monkeypatch):
    for directory in ("dashboard", "docs", "results", "runs", ".runtime", "game_lab"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "sentinel.txt").write_text("local review fixture")
    (tmp_path / "dashboard" / "index.html").write_text("local dashboard")
    (tmp_path / "serve.py").write_text("not a public asset")
    (tmp_path / "README.md").write_text("review guide")
    (tmp_path / "docs" / "forbidden_link").symlink_to(tmp_path / ".runtime" / "sentinel.txt")
    monkeypatch.setattr(serve, "ROOT", tmp_path)
    def request(method, path, host="127.0.0.1:8765", headers=None, raw_response=False):
        extra_headers = "".join(f"{key}: {value}\r\n" for key, value in (headers or {}).items())
        class Connection:
            def __init__(self):
                self.output = BytesIO()
            def makefile(self, mode, *args):
                return BytesIO(f"{method} {path} HTTP/1.0\r\nHost: {host}\r\n{extra_headers}\r\n".encode())
            def sendall(self, value):
                self.output.write(value)
        connection = Connection()
        serve.Handler(connection, ("127.0.0.1", 12345), SimpleNamespace(server_name="127.0.0.1", server_port=8765), directory=str(tmp_path))
        response = connection.output.getvalue()
        return response if raw_response else int(response.split(b" ", 2)[1])
    return request


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_only_review_assets_are_served(dashboard_server, method):
    for path in ("/runs/sentinel.txt", "/.runtime/sentinel.txt", "/game_lab/sentinel.txt",
                 "/serve.py", "/docs/%2e%2e/serve.py", "/docs/forbidden_link"):
        status = dashboard_server(method, path)
        assert status in (403, 404, 405), (method, path, status)


def test_allowed_assets_and_no_write_routes(dashboard_server):
    for method, path, expected in [("GET", "/", 302), ("GET", "/dashboard/index.html", 200), ("GET", "/docs/sentinel.txt", 200),
                                   ("GET", "/README.md", 200), ("GET", "/docs/", 404),
                                   ("GET", "/.", 404), ("HEAD", "/api/progress", 200),
                                   ("POST", "/api/progress", 501)]:
        status = dashboard_server(method, path)
        assert status == expected, (method, path, status)


def test_foreign_hosts_cannot_read_the_local_dashboard(dashboard_server):
    assert dashboard_server("GET", "/", "attacker.example") == 403
    assert dashboard_server("HEAD", "/README.md", "attacker.example") == 403


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_rebuilt_assets_ignore_stale_cache_validators(dashboard_server, method):
    response = dashboard_server(method, "/dashboard/sentinel.txt?v=2",
                                headers={"If-Modified-Since": "Sat, 01 Jan 2050 00:00:00 GMT"},
                                raw_response=True)
    header, _, body = response.partition(b"\r\n\r\n")
    assert header.startswith(b"HTTP/1.0 200 ")
    assert b"Cache-Control: no-store\r\n" in header + b"\r\n"
    assert body == (b"local review fixture" if method == "GET" else b"")
