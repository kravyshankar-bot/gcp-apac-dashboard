#!/usr/bin/env python3
"""
Project Time Tracker — simple multi-user web server.
Stores data in data.json (same directory). No external dependencies.

Usage:
    python3 server.py          # runs on port 8080
    python3 server.py 9000     # runs on a custom port
"""

import json
import csv
import io
import os
import sys
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
HTML_FILE = os.path.join(os.path.dirname(__file__), "index.html")


def load_entries():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_entries(entries):
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def calc_hours(start: str, end: str) -> float:
    """Return decimal hours between two HH:MM strings."""
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return round(((eh * 60 + em) - (sh * 60 + sm)) / 60, 4)


def entries_to_csv(entries):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date", "Client", "Project", "Job Number", "Task", "Start Time", "End Time", "Hours"])
    for e in entries:
        writer.writerow([
            e.get("id", ""),
            e.get("date", ""),
            e.get("client", ""),
            e.get("project", ""),
            e.get("jobNumber", ""),
            e.get("task", ""),
            e.get("startTime", ""),
            e.get("endTime", ""),
            e.get("hours", ""),
        ])
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} — {fmt % args}")

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, code, body: bytes, content_type="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/"):
            with open(HTML_FILE, "rb") as f:
                self.send_html(200, f.read())

        elif path == "/api/entries":
            self.send_json(200, load_entries())

        elif path == "/api/export":
            entries = load_entries()
            csv_data = entries_to_csv(entries).encode()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", f'attachment; filename="timesheet_{stamp}.csv"')
            self.send_header("Content-Length", str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data)

        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/entries":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                entry = json.loads(body)
            except json.JSONDecodeError:
                self.send_json(400, {"error": "invalid JSON"})
                return

            required = ["date", "client", "project", "jobNumber", "task", "startTime", "endTime"]
            missing = [f for f in required if not entry.get(f)]
            if missing:
                self.send_json(400, {"error": f"missing fields: {', '.join(missing)}"})
                return

            start, end = entry["startTime"], entry["endTime"]
            if end <= start:
                self.send_json(400, {"error": "endTime must be after startTime"})
                return
            entry["hours"] = calc_hours(start, end)
            entry["id"] = str(uuid.uuid4())
            entry["createdAt"] = datetime.utcnow().isoformat() + "Z"
            entries = load_entries()
            entries.append(entry)
            save_entries(entries)
            self.send_json(201, entry)
        else:
            self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        # DELETE /api/entries/<id>
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "entries":
            entry_id = parts[2]
            entries = load_entries()
            new_entries = [e for e in entries if e.get("id") != entry_id]
            if len(new_entries) == len(entries):
                self.send_json(404, {"error": "entry not found"})
                return
            save_entries(new_entries)
            self.send_json(200, {"deleted": entry_id})
        else:
            self.send_json(404, {"error": "not found"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), Handler)
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n  Project Time Tracker")
    print(f"  ─────────────────────────────────────")
    print(f"  Local:    http://localhost:{port}")
    print(f"  Network:  http://{local_ip}:{port}  ← share this with your team")
    print(f"  Data:     {DATA_FILE}")
    print(f"  Stop:     Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
