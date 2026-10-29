#!/usr/bin/env python3
"""Exercise a NAS backup claim without touching application data."""

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KUBECONFIGS = {
    "app-cluster": ROOT / "kubeconfig",
    "infra-cluster": ROOT / ".private/infra-cluster/kubeconfig",
}
RESTIC_IMAGE = "restic/restic:0.19.1"
PROBE = r"""
set -eu
umask 077
mkdir -p "/backup/$BACKUP_CLUSTER" /work/source
export RESTIC_REPOSITORY
RESTIC_REPOSITORY=$(mktemp -d "/backup/$BACKUP_CLUSTER/.target-probe.XXXXXX")
export RESTIC_PASSWORD
RESTIC_PASSWORD=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
export RESTIC_CACHE_DIR=/work/cache
printf 'NAS backup target probe: %s\n' "$BACKUP_CLUSTER" > /work/source/probe
restic init
restic backup /work/source --host "target-probe-$BACKUP_CLUSTER"
restic check --read-data
if RESTIC_PASSWORD=deliberately-wrong restic snapshots >/dev/null 2>&1; then
  echo 'ERROR: repository accepted the wrong encryption password' >&2
  exit 1
fi
restic restore latest --target /work/restored
cmp /work/source/probe /work/restored/work/source/probe
rm -rf "$RESTIC_REPOSITORY"
echo "PASS: $BACKUP_CLUSTER mount, encrypted backup, integrity check and byte-identical restore"
"""


def manifest(cluster, namespace, claim):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": f"backup-target-probe-{uuid.uuid4().hex[:8]}",
            "namespace": namespace,
            "labels": {"app.kubernetes.io/name": "backup-target-probe"},
        },
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 240,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "spec": {
                    "automountServiceAccountToken": False,
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "restic",
                        "image": RESTIC_IMAGE,
                        "command": ["/bin/sh", "-ec", PROBE],
                        "env": [{"name": "BACKUP_CLUSTER", "value": cluster}],
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "resources": {
                            "requests": {"cpu": "50m", "memory": "64Mi"},
                            "limits": {"cpu": "500m", "memory": "512Mi"},
                        },
                        "volumeMounts": [
                            {"name": "backup", "mountPath": "/backup"},
                            {"name": "work", "mountPath": "/work"},
                            {"name": "tmp", "mountPath": "/tmp"},
                        ],
                    }],
                    "volumes": [
                        {"name": "backup", "persistentVolumeClaim": {"claimName": claim}},
                        {"name": "work", "emptyDir": {"sizeLimit": "64Mi"}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}},
                    ],
                },
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=KUBECONFIGS)
    parser.add_argument("--namespace", default="backups")
    parser.add_argument("--claim", default="k8s-backup")
    parser.add_argument("--render", action="store_true", help="print Job JSON only")
    args = parser.parse_args()
    job = manifest(args.cluster, args.namespace, args.claim)
    if args.render:
        print(json.dumps(job, indent=2))
        return 0

    kubeconfig = KUBECONFIGS[args.cluster]
    if not kubeconfig.is_file():
        parser.error(f"Missing kubeconfig: {kubeconfig}")
    kubectl = ["kubectl", "--kubeconfig", str(kubeconfig), "-n", args.namespace]
    subprocess.run(kubectl + ["get", "pvc", args.claim], check=True)
    subprocess.run(kubectl + ["create", "-f", "-"], input=json.dumps(job), text=True, check=True)
    name = job["metadata"]["name"]
    result = subprocess.run(kubectl + ["wait", "--for=condition=Complete", f"job/{name}", "--timeout=260s"])
    subprocess.run(kubectl + ["logs", f"job/{name}", "--all-containers=true"])
    if result.returncode:
        subprocess.run(kubectl + ["describe", "job", name])
        print(f"Probe failed; inspect job/{name} and its pods. Disposable .target-probe directories may remain.", file=sys.stderr)
        return 1
    subprocess.run(kubectl + ["delete", "job", name, "--wait=true"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
