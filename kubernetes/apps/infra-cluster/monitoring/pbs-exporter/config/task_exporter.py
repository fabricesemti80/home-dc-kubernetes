#!/usr/bin/env python3
"""Report latest PBS backup and maintenance task outcomes without task messages."""
import json
import os
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ENDPOINT = "https://pbs.krapulax.home:8007/api2/json/nodes/localhost/tasks?limit=1000"
TOKEN_FILE = Path(os.environ.get("PBS_API_TOKEN_FILE", "/etc/pbs-credentials/PBS_MONITORING_TOKEN_SECRET"))
CA = os.environ.get("SSL_CERT_FILE", "/etc/pbs-ca/ca.pem")
TASK_TYPE = re.compile(r"^(?:backup|prune|verify.*|verification.*|garbage_collection|sync.*)$")
METRIC_HELP = {
    "pbs_task_collector_scrape_success": "Whether the PBS task API was read successfully.",
    "pbs_task_history_limit_reached": "Whether the PBS task API returned the maximum requested tasks.",
    "pbs_task_latest_outcome": "Outcome of the latest completed task for each task identity.",
    "pbs_task_latest_finished_timestamp_seconds": "Completion time of the latest completed task in seconds since the Unix epoch.",
}
METADATA = "".join(f"# HELP {name} {description}\n# TYPE {name} gauge\n" for name, description in METRIC_HELP.items())


def label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def summarize(tasks):
    latest = {}
    for task in tasks:
        task_type = str(task.get("worker_type") or "")
        task_id = str(task.get("worker_id") or "")
        end = task.get("endtime")
        if not TASK_TYPE.fullmatch(task_type) or not isinstance(end, (int, float)) or isinstance(end, bool):
            continue
        key = (task_type, task_id)
        if key not in latest or end > latest[key][0]:
            status = str(task.get("status") or "")
            outcome = "success" if status == "OK" else "warning" if status.startswith("WARNINGS") else "error" if status else "unknown"
            latest[key] = (end, outcome)
    return latest


def scrape():
    try:
        token = TOKEN_FILE.read_text().strip()
        if not token:
            raise ValueError("Empty PBS monitoring token")
        context = ssl.create_default_context(cafile=CA)
        req = Request(ENDPOINT, headers={"Authorization": "PBSAPIToken=prometheus@pbs!victoriametrics:" + token})
        with urlopen(req, context=context, timeout=15) as response:
            tasks = json.load(response)["data"]
        if not isinstance(tasks, list):
            raise ValueError("Unexpected PBS task response")
        metrics = ["pbs_task_collector_scrape_success 1", f"pbs_task_history_limit_reached {int(len(tasks) >= 1000)}"]
        for (task_type, task_id), (ended, outcome) in sorted(summarize(tasks).items()):
            labels = f'task_type="{label(task_type)}",task_id="{label(task_id)}"'
            metrics.append(f'pbs_task_latest_outcome{{{labels},outcome="{outcome}"}} 1')
            metrics.append(f"pbs_task_latest_finished_timestamp_seconds{{{labels}}} {ended}")
        return METADATA + "\n".join(metrics) + "\n"
    except Exception:
        # API responses and auth headers must not be exposed in metrics or logs.
        return METADATA + "pbs_task_collector_scrape_success 0\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = b"ok\n"
        elif self.path == "/metrics":
            body = scrape().encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 10020), Handler).serve_forever()
