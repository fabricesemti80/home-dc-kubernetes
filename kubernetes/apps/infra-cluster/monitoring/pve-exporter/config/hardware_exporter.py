#!/usr/bin/env python3
"""Expose selected PVE disk SMART and ZFS health through the audit-only API."""
import json
import os
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://10.0.40.10:8006/api2/json"
CA = os.environ.get("REQUESTS_CA_BUNDLE", "/etc/pve-ca/ca.pem")
TOKEN_FILE = Path(os.environ.get("PVE_TOKEN_VALUE_FILE", "/etc/pve-credentials/PVE_MONITORING_TOKEN_SECRET"))
DEVICE = re.compile(r"^/dev/(?:nvme\d+n\d+|sd[a-z]+)$")
NVME_TEMPERATURE = re.compile(r"^Temperature:\s+(\d+)\s+Celsius", re.MULTILINE)
METRIC_HELP = {
    "pve_hardware_disk_health_info": "Current PVE-reported SMART disk health.",
    "pve_hardware_disk_wearout_percent": "PVE-reported disk wearout percentage.",
    "pve_hardware_smart_scrape_success": "Whether the PVE SMART endpoint was read successfully.",
    "pve_hardware_disk_temperature_celsius": "PVE-reported SMART disk temperature in Celsius.",
    "pve_hardware_zpool_health_info": "Current PVE-reported ZFS pool health.",
    "pve_hardware_scrape_success": "Whether PVE disk and ZFS endpoints were read successfully.",
}
METADATA = "".join(f"# HELP {name} {description}\n# TYPE {name} gauge\n" for name, description in METRIC_HELP.items())


def label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def request(path, context, token):
    req = Request(API + path, headers={"Authorization": "PVEAPIToken=prometheus@pve!victoriametrics=" + token})
    with urlopen(req, context=context, timeout=8) as response:
        return json.load(response)["data"]


def temperature(smart):
    if smart.get("type") == "text":
        match = NVME_TEMPERATURE.search(smart.get("text", ""))
        return int(match.group(1)) if match else None
    for attr in smart.get("attributes", []):
        if str(attr.get("id")) in {"190", "194"} and "temp" in str(attr.get("name", "")).lower():
            match = re.match(r"^\s*(\d+)", str(attr.get("raw", "")))
            if match:
                return int(match.group(1))
    return None


def scrape():
    result = []
    try:
        token = TOKEN_FILE.read_text().strip()
        if not token:
            raise ValueError("Empty monitoring token")
        context = ssl.create_default_context(cafile=CA)
        disks = request("/nodes/pve-00/disks/list", context, token)
        pools = request("/nodes/pve-00/disks/zfs", context, token)
        if not isinstance(disks, list) or not isinstance(pools, list):
            raise ValueError("Unexpected PVE API response")
        for disk in disks:
            device = str(disk.get("devpath", ""))
            if not DEVICE.fullmatch(device):
                continue
            escaped = label(device)
            health = label(disk.get("health") or "UNKNOWN")
            result.append(f'pve_hardware_disk_health_info{{device="{escaped}",health="{health}"}} 1')
            wear = disk.get("wearout")
            if isinstance(wear, (int, float)) and not isinstance(wear, bool):
                result.append(f'pve_hardware_disk_wearout_percent{{device="{escaped}"}} {wear}')
            try:
                smart = request("/nodes/pve-00/disks/smart?" + urlencode({"disk": device}), context, token)
                measured = temperature(smart)
                result.append(f'pve_hardware_smart_scrape_success{{device="{escaped}"}} 1')
                if measured is not None:
                    result.append(f'pve_hardware_disk_temperature_celsius{{device="{escaped}"}} {measured}')
            except Exception:
                result.append(f'pve_hardware_smart_scrape_success{{device="{escaped}"}} 0')
        for pool in pools:
            name = label(pool.get("name", ""))
            if not name:
                continue
            health = label(pool.get("health") or "UNKNOWN")
            result.append(f'pve_hardware_zpool_health_info{{pool="{name}",health="{health}"}} 1')
        result.append("pve_hardware_scrape_success 1")
    except Exception:
        # Do not expose API errors, response bodies, token values or headers.
        result = ["pve_hardware_scrape_success 0"]
    return METADATA + "\n".join(result) + "\n"


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
    ThreadingHTTPServer(("0.0.0.0", 9232), Handler).serve_forever()
