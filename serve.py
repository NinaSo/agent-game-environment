"""Read-only local dashboard. No inference or write endpoints."""

import json
from contextlib import closing
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from game_lab.store import connect, manifest, status

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        # Rebuilt data and scripts must never mix with timestamp-cached versions.
        if "If-Modified-Since" in self.headers:
            del self.headers["If-Modified-Since"]
        return super().send_head()

    def permitted_route(self):
        try:
            host = urlsplit("//" + self.headers.get("Host", "")).hostname
        except ValueError:
            host = None
        if host not in {"127.0.0.1", "localhost"}:
            self.send_error(403)
            return None
        route = unquote(urlsplit(self.path).path)
        if route == "/api/progress":
            return route
        if route == "/":
            self.send_response(302)
            self.send_header("Location", "/dashboard/index.html")
            self.end_headers()
            return None
        resolved = (ROOT / route.lstrip("/")).resolve()
        relative = resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else None
        allowed = (
            relative is not None
            and bool(relative.parts)
            and (
                relative.parts[0] in {"dashboard", "results", "docs"}
                or resolved == ROOT / "README.md"
            )
        )
        if not allowed or not resolved.is_file():
            self.send_error(404)
            return None
        return route

    def do_HEAD(self):
        route = self.permitted_route()
        if route is None:
            return
        if route == "/api/progress":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        route = self.permitted_route()
        if route is None:
            return
        if route == "/api/progress":
            runs = []
            for path in sorted((ROOT / "runs").glob("*.sqlite")):
                with closing(connect(path.resolve(), readonly=True)) as db:
                    db.execute("BEGIN")
                    s = status(db)
                    m = manifest(db)
                    runs.append(
                        dict(
                            name=path.stem,
                            counts=s["episodes"],
                            episodes=len(m["config"]["episodes"]),
                            rounds=s["completed_rounds"],
                            attempts=sum(s["attempts"].values()),
                        )
                    )
            existing = {r["name"] for r in runs}
            for path in sorted((ROOT / "configs").glob("*.json")):
                if path.stem not in existing:
                    count = len(json.loads(path.read_text())["episodes"])
                    runs.append(
                        dict(
                            name=path.stem,
                            counts={"pending": count},
                            episodes=count,
                            rounds=0,
                            attempts=0,
                        )
                    )
            body = json.dumps({"runs": runs}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8765), partial(Handler, directory=str(ROOT))
    )
    print("Local dashboard: http://127.0.0.1:8765", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
