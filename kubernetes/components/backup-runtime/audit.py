"""Check expected logical sources, native success provenance and repository health."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc


def instant(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def succeeded(backup):
    return any(
        c["type"] == "Completed"
        and c["status"] == "True"
        and c.get("reason") == "Succeeded"
        for c in backup.get("status", {}).get("conditions", [])
    )


def matches(labels, selectors):
    for selector in selectors:
        if not all(
            labels.get(k) == v for k, v in selector.get("matchLabels", {}).items()
        ):
            continue
        accepted = True
        for expression in selector.get("matchExpressions", []):
            key, operator = expression["key"], expression["operator"]
            values = expression.get("values", [])
            if operator == "In":
                accepted &= key in labels and labels[key] in values
            elif operator == "NotIn":
                accepted &= key not in labels or labels[key] not in values
            elif operator == "Exists":
                accepted &= key in labels
            elif operator == "DoesNotExist":
                accepted &= key not in labels
            else:
                raise ValueError("Unknown selector operator")
        if accepted:
            return True
    return False


def coverage(sources, backups, jobs, snapshots, namespace, repository, now):
    """A snapshot alone (including one left by a failed producer) is not coverage."""
    report, problems = {}, []
    for app, source in sources.items():
        labels = {
            "backup.krapulax.dev/app": app,
            "backup.krapulax.dev/policy": source["profile"],
            "backup.krapulax.dev/strategy": "postgres-dump",
        }
        accepted = []
        latest_failure = None
        for backup in backups:
            spec = backup["spec"]
            operation_labels = backup["metadata"].get("labels", {})
            candidate_labels = dict(labels)
            if (
                operation_labels.get("backup.krapulax.dev/app") == app
                and operation_labels.get("backup.krapulax.dev/policy")
                == source["profile"]
            ):
                for key in [
                    "backup.krapulax.dev/operation",
                    "backup.krapulax.dev/proof-id",
                ]:
                    if key in operation_labels:
                        candidate_labels[key] = operation_labels[key]
            if spec.get("backend", {}).get("local", {}).get("mountPath") != repository:
                continue
            if not matches(candidate_labels, spec.get("labelSelectors", [])):
                continue
            owned = [
                j
                for j in jobs
                if any(
                    o.get("uid") == backup["metadata"]["uid"]
                    for o in j["metadata"].get("ownerReferences", [])
                )
            ]
            start = instant(backup["metadata"]["creationTimestamp"])
            failed = backup.get("status", {}).get("finished") and not succeeded(backup)
            failed |= any(
                j.get("status", {}).get("failed", 0)
                and not j["status"].get("active")
                and not j["status"].get("succeeded")
                for j in owned
            )
            if failed:
                latest_failure = max(latest_failure or start, start)
            if (
                not succeeded(backup)
                or not owned
                or not all(
                    j.get("status", {}).get("succeeded", 0)
                    and j["status"].get("completionTime")
                    for j in owned
                )
            ):
                continue
            end = max(instant(j["status"]["completionTime"]) for j in owned)
            for snapshot in snapshots:
                item = snapshot["spec"]
                if item.get("repository") != repository or item.get("paths") != [
                    f"/{namespace}-{app}.tar"
                ]:
                    continue
                if not re.fullmatch(r"[0-9a-f]{64}", item.get("id", "")):
                    continue
                if start <= instant(item["date"]) <= end:
                    accepted.append((start, item))
        if not accepted:
            problems.append(
                f"{app}: no successful native capture with its exact snapshot path"
            )
            continue
        start, snapshot = max(accepted, key=lambda pair: pair[0])
        report[app] = {
            "snapshot": snapshot["id"],
            "capture_window_start": start.isoformat(),
            "snapshot_date": snapshot["date"],
        }
        if now - start > dt.timedelta(hours=8) or start > now:
            problems.append(
                f"{app}: capture is stale or has an invalid future timestamp (8-hour limit)"
            )
        if latest_failure and latest_failure > start:
            problems.append(f"{app}: a newer capture failed")
    if not sources:
        problems.append(
            "Policy has no expected sources; zero-source success is not protection"
        )
    return report, problems


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class API:
    def __init__(self):
        root = Path("/var/run/backup-api")
        self.token = (root / "token").read_text()
        self.opener = urllib.request.build_opener(
            NoRedirect(),
            urllib.request.HTTPSHandler(
                context=ssl.create_default_context(cafile=str(root / "ca.crt"))
            ),
        )
        self.base = (
            "https://"
            + os.environ["KUBERNETES_SERVICE_HOST"]
            + ":"
            + os.environ["KUBERNETES_SERVICE_PORT_HTTPS"]
        )

    def items(self, prefix, namespace, resource):
        request = urllib.request.Request(
            f"{self.base}/{prefix}/namespaces/{namespace}/{resource}",
            headers={"Authorization": "Bearer " + self.token},
        )
        with self.opener.open(request, timeout=20) as response:
            return json.load(response)["items"]


def notify(message):
    url = os.environ["SLACK_WEBHOOK_URL"]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "hooks.slack.com":
        raise ValueError("Alert route must be an HTTPS Slack incoming webhook")
    request = urllib.request.Request(
        url,
        data=json.dumps({"text": message}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=20
    ) as response:
        if response.status != 200 or response.read(16).strip() != b"ok":
            raise RuntimeError("Slack did not acknowledge the alert")


def main():
    cluster, namespace = os.environ["BACKUP_CLUSTER"], os.environ["POD_NAMESPACE"]
    repository = f"/repository/{cluster}/{namespace}/critical-6h"
    state_file = Path(
        os.environ.get(
            "AUDIT_STATE_PATH", str(Path(repository).parent / ".critical-6h-audit.json")
        )
    )
    now = dt.datetime.now(UTC)
    report, problems = {}, []
    try:
        sources = {
            a: s
            for a, s in json.loads(Path("/scripts/sources.json").read_text()).items()
            if s["cluster"] == cluster and s["namespace"] == namespace
        }
        api = API()
        backups = api.items("apis/k8up.io/v1", namespace, "backups")
        jobs = api.items("apis/batch/v1", namespace, "jobs")
        snapshots = api.items("apis/k8up.io/v1", namespace, "snapshots")
        report, problems = coverage(
            sources, backups, jobs, snapshots, namespace, repository, now
        )
        checks = api.items("apis/k8up.io/v1", namespace, "checks")
        latest_metadata = instant(os.environ["FULL_CHECK_BASELINE"])
        failed_metadata = []
        for check in checks:
            if (
                check["spec"].get("backend", {}).get("local", {}).get("mountPath")
                != repository
            ):
                continue
            created = instant(check["metadata"]["creationTimestamp"])
            if succeeded(check):
                latest_metadata = max(latest_metadata, created)
            elif check.get("status", {}).get("finished"):
                failed_metadata.append(created)
        if now - latest_metadata > dt.timedelta(days=8):
            problems.append("Repository metadata check is overdue (8-day limit)")
        if any(created > latest_metadata for created in failed_metadata):
            problems.append("Repository metadata check failed")
        full_checks = [
            j
            for j in jobs
            if j["metadata"].get("labels", {}).get("backup.krapulax.dev/maintenance")
            == "read-data"
        ]
        latest_full = instant(os.environ["FULL_CHECK_BASELINE"])
        for job in full_checks:
            if job.get("status", {}).get("succeeded"):
                latest_full = max(latest_full, instant(job["status"]["completionTime"]))
        if now - latest_full > dt.timedelta(days=35):
            problems.append("Full repository data check is overdue (35-day limit)")
        if any(
            j.get("status", {}).get("failed", 0)
            and not j["status"].get("active")
            and not j["status"].get("succeeded")
            and instant(j["metadata"]["creationTimestamp"]) > latest_full
            for j in full_checks
        ):
            problems.append("Full repository data check failed")
        capacity = os.statvfs("/repository")
        if not capacity.f_blocks or capacity.f_bavail / capacity.f_blocks < 0.20:
            problems.append("NAS filesystem has less than 20% available capacity")
    except Exception:
        problems.append(
            "Coverage audit could not complete; inspect its namespace and API/storage access"
        )
    problems = sorted(set(problems))
    previous = {}
    try:
        previous = json.loads(state_file.read_text())
    except (OSError, ValueError):
        pass
    fingerprint = hashlib.sha256(json.dumps(problems).encode()).hexdigest()
    changed = previous.get("fingerprint") != fingerprint
    reminder = now.timestamp() - previous.get("notified_at", 0) > 86400
    should_notify = (
        (bool(problems) and (changed or reminder))
        or (not problems and bool(previous.get("unhealthy")))
        or os.environ.get("NOTIFY_ALWAYS") == "true"
    )
    notified_at = previous.get("notified_at", 0)
    if should_notify:
        title = "BACKUP ATTENTION" if problems else "BACKUP COVERAGE OK"
        details = (
            "\n".join(problems)
            if problems
            else ", ".join(sorted(report)) + ": fresh, proven-native captures"
        )
        try:
            notify(
                f"{title} — {cluster}/{namespace}\n{details}\nSame-NAS database coverage only; not an offsite or complete-photo backup."
            )
            notified_at = now.timestamp()
        except Exception as error:
            raise RuntimeError(
                "Backup alert delivery failed; webhook details suppressed"
            ) from None
    result = {
        "cluster": cluster,
        "namespace": namespace,
        "sources": report,
        "problems": problems,
        "notification_delivered": should_notify,
    }
    print(json.dumps(result, sort_keys=True), flush=True)
    try:
        state_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = state_file.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(
                {
                    "fingerprint": fingerprint,
                    "unhealthy": bool(problems),
                    "notified_at": notified_at,
                },
                output,
            )
        os.replace(temporary, state_file)
    except OSError:
        raise RuntimeError(
            "Audit state cannot be persisted; notification suppression is unavailable"
        ) from None
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
