#!/usr/bin/env python3
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
HOST, PORT = "0.0.0.0", 8000
OUTPUT_FILE = ROOT / "output" / "bildentscheidungen.json"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_POST(self):
        if self.path.rstrip("/") == "/save-decisions":
            self._handle_save()
            return
        self.send_error(404, "Not Found")

    def _handle_save(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
            decisions = payload.get("decisions")
            if not isinstance(decisions, list):
                raise ValueError("decisions muss ein Array sein")
        except Exception as exc:  # noqa: BLE001 - klarer Fehlertext
            self.send_error(400, f"Ungültige JSON: {exc}")
            return

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(
            json.dumps(decisions, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        resp = {
            "status": "ok",
            "path": str(OUTPUT_FILE.relative_to(ROOT)),
            "count": len(decisions),
        }
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        print(f"Serving {ROOT} at http://{HOST}:{PORT}")
        print("POST /save-decisions -> writes output/bildentscheidungen.json")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server...")


if __name__ == "__main__":
    main()
