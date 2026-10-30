#!/usr/bin/env python3
"""Call upstream Backrest APIs through a private exact-pod tunnel."""

import argparse
import contextlib
import json
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace
import urllib.error
import urllib.request
import uuid

from backup_transport import port_forward

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@contextlib.contextmanager
def client(cluster):
    config = "apps" if cluster == "app-cluster" else "infra"
    kubeconfig = ROOT / (
        "kubeconfig" if config == "apps" else ".private/infra-cluster/kubeconfig"
    )
    resources = SimpleNamespace(
        kubectl=["kubectl", "--kubeconfig", str(kubeconfig)], namespace="backups"
    )
    result = subprocess.run(
        resources.kubectl
        + [
            "-n",
            "backups",
            "get",
            "pods",
            "-l",
            "app.kubernetes.io/instance=backrest",
            "-o",
            "json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    pods = [
        pod
        for pod in json.loads(result.stdout)["items"]
        if not pod["metadata"].get("deletionTimestamp")
        and any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in pod["status"].get("conditions", [])
        )
    ]
    if len(pods) != 1:
        raise RuntimeError("Expected exactly one ready Backrest instance")
    credential = subprocess.run(
        [
            "doppler",
            "secrets",
            "get",
            "BACKREST_ADMIN_PASSWORD",
            "--project",
            "home-dc-kubernetes",
            "--config",
            config,
            "--plain",
        ],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.removesuffix("\n")
    with port_forward(resources, pods[0]["metadata"]["name"], 9898) as address:
        opener = urllib.request.build_opener(NoRedirect())
        token = None

        def call(service, method, value=None):
            headers = {
                "Content-Type": "application/json",
                "Connect-Protocol-Version": "1",
            }
            if token:
                headers["Authorization"] = "Bearer " + token
            request = urllib.request.Request(
                address + "/v1." + service + "/" + method,
                data=json.dumps(value or {}).encode(),
                headers=headers,
                method="POST",
            )
            try:
                timeout = 14400 if method in {"Backup", "Restore", "DoRepoTask"} else 60
                with opener.open(request, timeout=timeout) as response:
                    return json.load(response)
            except (urllib.error.URLError, ValueError):
                raise RuntimeError(
                    f"Backrest {method} failed; credential-bearing response suppressed"
                ) from None

        token = call(
            "Authentication", "Login", {"username": "admin", "password": credential}
        )["token"]
        yield lambda method, value=None: call("Backrest", method, value), resources


def require_recovery(call, cluster):
    """Require real native restore history, not only a successful backup."""
    plans = (
        ["immich-db", "immich-originals"]
        if cluster == "app-cluster"
        else ["litellm-db"]
    )
    for plan in plans:
        snapshots = call("ListSnapshots", {"repoId": "nas", "planId": plan}).get(
            "snapshots", []
        )
        ids = {snapshot["id"] for snapshot in snapshots}
        operations = call(
            "GetOperations", {"selector": {"planId": plan}, "lastN": 1000}
        ).get("operations", [])
        cutoff = (time.time() - (30 if plan == "immich-originals" else 8) * 3600) * 1000
        fresh = {
            op.get("snapshotId")
            for op in operations
            if op.get("status") == "STATUS_SUCCESS"
            and "operationBackup" in op
            and int(op.get("unixTimeStartMs", 0)) >= cutoff
        }
        if not any(
            op.get("status") == "STATUS_SUCCESS"
            and "operationRestore" in op
            and op.get("snapshotId") in ids & fresh
            for op in operations
        ):
            raise RuntimeError(
                f"{plan}: no successful restore of a fresh existing replacement snapshot; legacy deletion refused"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["run", "check", "snapshots", "restore", "status", "recovery-gate"],
    )
    parser.add_argument("cluster", choices=["app-cluster", "infra-cluster"])
    parser.add_argument("--plan")
    parser.add_argument("--snapshot")
    args = parser.parse_args()
    if args.action in ["run", "restore"] and not args.plan:
        parser.error("--plan is required")
    if args.action == "restore" and (
        not args.snapshot or not re.fullmatch(r"[0-9a-f]{64}", args.snapshot)
    ):
        parser.error("restore requires --snapshot with a full immutable ID")
    with client(args.cluster) as (call, resources):
        if args.action == "run":
            call("Backup", {"value": args.plan})
            print(json.dumps({"plan": args.plan, "backup_completed": True}))
        elif args.action == "check":
            print(
                json.dumps(call("DoRepoTask", {"repoId": "nas", "task": "TASK_CHECK"}))
            )
        elif args.action == "snapshots":
            snapshots = call(
                "ListSnapshots", {"repoId": "nas", "planId": args.plan or ""}
            ).get("snapshots", [])
            print(
                json.dumps(
                    [
                        {
                            key: row[key]
                            for key in ["id", "time", "paths", "tags"]
                            if key in row
                        }
                        for row in snapshots
                    ]
                )
            )
        elif args.action == "restore":
            target = (
                "/backups/" + args.cluster + "/backrest/restores/" + uuid.uuid4().hex
            )
            subprocess.run(
                resources.kubectl
                + [
                    "-n",
                    "backups",
                    "exec",
                    "deployment/backrest",
                    "-c",
                    "app",
                    "--",
                    "sh",
                    "-ec",
                    'umask 077; test ! -e "$1"; mkdir -p "$(dirname "$1")"',
                    "--",
                    target,
                ],
                check=True,
                capture_output=True,
            )
            result = call(
                "Restore",
                {
                    "repoId": "nas",
                    "planId": args.plan,
                    "snapshotId": args.snapshot,
                    "path": "/",
                    "target": target,
                },
            )
            print(
                json.dumps(
                    {
                        "queued": True,
                        "completion_verified": False,
                        "target": target,
                        **result,
                    }
                )
            )
        elif args.action == "recovery-gate":
            require_recovery(call, args.cluster)
            print(
                json.dumps(
                    {
                        "replacement_file_restores_verified": True,
                        "database_import_still_requires_operator_verification": True,
                    }
                )
            )
        else:
            operations = call("GetOperations", {"selector": {}, "lastN": 20}).get(
                "operations", []
            )
            print(
                json.dumps(
                    [
                        {
                            key: row[key]
                            for key in [
                                "id",
                                "planId",
                                "status",
                                "snapshotId",
                                "unixTimeStartMs",
                                "unixTimeEndMs",
                            ]
                            if key in row
                        }
                        for row in operations
                    ]
                )
            )


if __name__ == "__main__":
    try:
        main()
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        raise SystemExit("ERROR: " + str(error)) from None
