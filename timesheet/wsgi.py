"""
WSGI entry point for PythonAnywhere hosting.
For local use, run server.py instead.
"""

import csv
import io
import json
import os
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
HTML_FILE = os.path.join(BASE_DIR, "index.html")


def load_entries():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_entries(entries):
    with open(DATA_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def calc_hours(start, end):
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


def json_response(start_response, code, data):
    body = json.dumps(data).encode()
    start_response(code, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("Access-Control-Allow-Origin", "*"),
    ])
    return [body]


def application(environ, start_response):
    method = environ["REQUEST_METHOD"]
    path = environ.get("PATH_INFO", "/").rstrip("/") or "/"

    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return [b""]

    # Serve the frontend
    if method == "GET" and path == "/":
        with open(HTML_FILE, "rb") as f:
            body = f.read()
        start_response("200 OK", [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]

    # List entries
    if method == "GET" and path == "/api/entries":
        return json_response(start_response, "200 OK", load_entries())

    # CSV export
    if method == "GET" and path == "/api/export":
        csv_data = entries_to_csv(load_entries()).encode()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        start_response("200 OK", [
            ("Content-Type", "text/csv"),
            ("Content-Disposition", f'attachment; filename="timesheet_{stamp}.csv"'),
            ("Content-Length", str(len(csv_data))),
        ])
        return [csv_data]

    # Add entry
    if method == "POST" and path == "/api/entries":
        length = int(environ.get("CONTENT_LENGTH", 0))
        body = environ["wsgi.input"].read(length)
        try:
            entry = json.loads(body)
        except json.JSONDecodeError:
            return json_response(start_response, "400 Bad Request", {"error": "invalid JSON"})

        required = ["date", "client", "project", "task", "startTime", "endTime"]
        missing = [f for f in required if not entry.get(f)]
        if missing:
            return json_response(start_response, "400 Bad Request",
                                 {"error": f"missing fields: {', '.join(missing)}"})

        if entry["endTime"] <= entry["startTime"]:
            return json_response(start_response, "400 Bad Request",
                                 {"error": "endTime must be after startTime"})

        entry["hours"] = calc_hours(entry["startTime"], entry["endTime"])
        entry["id"] = str(uuid.uuid4())
        entry["createdAt"] = datetime.utcnow().isoformat() + "Z"
        entries = load_entries()
        entries.append(entry)
        save_entries(entries)
        return json_response(start_response, "201 Created", entry)

    # Delete entry
    if method == "DELETE" and path.startswith("/api/entries/"):
        entry_id = path.split("/")[-1]
        entries = load_entries()
        new_entries = [e for e in entries if e.get("id") != entry_id]
        if len(new_entries) == len(entries):
            return json_response(start_response, "404 Not Found", {"error": "entry not found"})
        save_entries(new_entries)
        return json_response(start_response, "200 OK", {"deleted": entry_id})

    return json_response(start_response, "404 Not Found", {"error": "not found"})
