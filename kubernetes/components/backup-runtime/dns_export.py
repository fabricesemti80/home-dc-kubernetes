"""Native exact-instance Technitium export; no source configuration mutations."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

FLAGS = {key: "true" for key in ["authConfig", "dnsSettings", "zones", "apps", "scopes", "allowedZones", "blockedZones", "webServiceSettings", "clusterConfig", "logSettings"]}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DnsAPI:
    def __init__(self, address, token=None):
        self.address, self.token = address, token
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, values=None, raw=False, file=None):
        headers = {}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if file is None:
            data = urllib.parse.urlencode(values or {}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            boundary = "backup-" + secrets.token_hex(16)
            parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode() for key, value in (values or {}).items()]
            parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="dns.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode() + file + b"\r\n", f"--{boundary}--\r\n".encode()]
            data = b"".join(parts)
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        try:
            request = urllib.request.Request(self.address + path, data=data, headers=headers, method="POST")
            with self.opener.open(request, timeout=90) as response:
                body = response.read(64 * 1024 * 1024 + 1)
                if len(body) > 64 * 1024 * 1024:
                    raise RuntimeError("DNS response exceeded its reviewed bound")
                if raw:
                    return body
                parsed = json.loads(body)
        except (urllib.error.URLError, OSError, ValueError):
            raise RuntimeError(f"DNS API transport/response failed at {path}; private response suppressed") from None
        if parsed.get("status") != "ok":
            raise RuntimeError(f"DNS API rejected {path}; private response suppressed")
        return parsed.get("response", parsed)


def inventory(api):
    result = []
    for zone in api.call("/api/zones/list")["zones"]:
        if zone.get("internal"):
            continue
        domain = zone["name"] or "."
        records = api.call("/api/zones/records/get", {"domain": domain, "zone": domain, "listZone": "true"})["records"]
        records = [{key: row[key] for key in ["name", "type", "ttl", "rData", "disabled", "comments"] if key in row} for row in records]
        records.sort(key=lambda row: json.dumps(row, sort_keys=True))
        result.append({"name": zone["name"], "type": zone["type"], "disabled": zone["disabled"], "records": records})
    return sorted(result, key=lambda row: row["name"])


def validate_zip(archive):
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        entries = zipped.infolist()
        if not entries or len(entries) > 10000 or sum(entry.file_size for entry in entries) > 256 * 1024 * 1024:
            raise RuntimeError("DNS native ZIP is empty or exceeds the reviewed expansion bound")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("Unsafe DNS native ZIP member")
        if zipped.testzip() is not None:
            raise RuntimeError("DNS native ZIP CRC validation failed")


def capture():
    stage = Path("/stage")
    source = json.loads((stage / "source.json").read_bytes())
    address = "http://" + (stage / "source-ip").read_text().strip() + ":5380"
    mode = os.environ["DNS_AUTH_MODE"]
    if mode not in {"token", "admin-session"}:
        raise RuntimeError("Unsupported DNS export authentication mode")
    admin = DnsAPI(address)
    admin.token = admin.call("/api/user/login", {"user": "admin", "pass": os.environ["DNS_RECOVERY_ADMIN_PASSWORD"]})["token"]
    try:
        exporter = DnsAPI(address, os.environ["DNS_CREDENTIAL"]) if mode == "token" else admin
        if mode == "token" and exporter.call("/api/user/session/get").get("username") != "k8up_backup":
            raise RuntimeError("DNS backup token belongs to the wrong principal")
        before = inventory(admin)
        archive = exporter.call("/api/settings/backup", FLAGS, raw=True)
        validate_zip(archive)
        if inventory(admin) != before:
            raise RuntimeError("DNS records changed during native export; no recovery set accepted")
    finally:
        admin.call("/api/user/logout")
    with tempfile.TemporaryDirectory(prefix="dns-", dir=stage) as temporary:
        root = Path(temporary)
        files = {"source.json": json.dumps(source, sort_keys=True).encode() + b"\n", "dns.zip": archive, "zones.json": json.dumps(before, sort_keys=True).encode() + b"\n", "recovery-admin-password": os.environ["DNS_RECOVERY_ADMIN_PASSWORD"].encode(), "dns.json": json.dumps({"format": 1, "app": source["app"], "auth_mode": mode, "native_export": True}, sort_keys=True).encode() + b"\n"}
        for name, value in files.items():
            (root / name).write_bytes(value)
            (root / name).chmod(0o600)
        (root / "SHA256SUMS").write_text("".join(hashlib.sha256(value).hexdigest() + "  " + name + "\n" for name, value in sorted(files.items())))
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:") as bundle:
            for path in sorted(root.iterdir()):
                bundle.add(path, arcname=path.name, recursive=False)
        sys.stdout.buffer.write(output.getvalue())


if __name__ == "__main__":
    try:
        capture()
    except (RuntimeError, OSError, ValueError, KeyError, zipfile.BadZipFile):
        raise SystemExit("Native DNS export failed; credentials and private diagnostics suppressed") from None
