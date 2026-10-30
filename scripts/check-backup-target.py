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
DEFAULT_UID = 1004
DEFAULT_GID = 65534
PROBE = r"""
set -eu
id
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
DENIAL_PROBE = r"""
set -eu
id
violations=0
for base in /backup "/backup/$BACKUP_CLUSTER"; do
  if result=$(mktemp -d "$base/.access-denial.XXXXXX" 2>&1); then
    rmdir "$result"
    echo "FAIL: unrelated UID can write $base"
    violations=1
  else
    printf '%s\n' "$result"
    case "$result" in
      *'Permission denied'*) echo "PASS: write denied at $base" ;;
      *) exit 1 ;;
    esac
  fi
done
test "$violations" -eq 0
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
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": DEFAULT_UID,
                        "runAsGroup": DEFAULT_GID,
                        "supplementalGroups": [],
                    },
                    "containers": [
                        {
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
                        }
                    ],
                    "volumes": [
                        {
                            "name": "backup",
                            "persistentVolumeClaim": {"claimName": claim},
                        },
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
    parser.add_argument("--uid", type=int, default=DEFAULT_UID)
    parser.add_argument("--gid", type=int, default=DEFAULT_GID)
    parser.add_argument(
        "--expect-denied",
        action="store_true",
        help="Require write denial at export root and cluster prefix",
    )
    parser.add_argument("--render", action="store_true", help="print Job JSON only")
    args = parser.parse_args()
    if args.uid < 1 or args.gid < 1:
        parser.error("Use an unprivileged, positive UID/GID")
    job = manifest(args.cluster, args.namespace, args.claim)
    pod_spec = job["spec"]["template"]["spec"]
    pod_spec["securityContext"].update(runAsUser=args.uid, runAsGroup=args.gid)
    if args.expect_denied:
        pod_spec["containers"][0]["command"] = ["/bin/sh", "-ec", DENIAL_PROBE]
        job["metadata"]["labels"]["backup.krapulax.dev/probe"] = "denial"
    if args.render:
        print(json.dumps(job, indent=2))
        return 0

    kubeconfig = KUBECONFIGS[args.cluster]
    if not kubeconfig.is_file():
        parser.error(f"Missing kubeconfig: {kubeconfig}")
    kubectl = ["kubectl", "--kubeconfig", str(kubeconfig), "-n", args.namespace]
    subprocess.run(kubectl + ["get", "pvc", args.claim], check=True)
    subprocess.run(
        kubectl + ["create", "-f", "-"], input=json.dumps(job), text=True, check=True
    )
    name = job["metadata"]["name"]
    result = subprocess.run(
        kubectl
        + [
            "wait",
            "--for=jsonpath={.status.conditions[0].status}=True",
            f"job/{name}",
            "--timeout=260s",
        ]
    )
    state = json.loads(
        subprocess.run(
            kubectl + ["get", "job", name, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    succeeded = any(
        condition["type"] in {"Complete", "SuccessCriteriaMet"}
        and condition["status"] == "True"
        for condition in state.get("status", {}).get("conditions", [])
    )
    subprocess.run(kubectl + ["logs", f"job/{name}", "--all-containers=true"])
    if result.returncode or not succeeded:
        subprocess.run(kubectl + ["describe", "job", name])
        if args.expect_denied:
            print(
                f"NFS isolation gate failed; inspect job/{name}. Do not enable production backups until the denial check passes.",
                file=sys.stderr,
            )
        else:
            print(
                f"Probe failed; inspect job/{name} and its pods. Disposable .target-probe directories may remain.",
                file=sys.stderr,
            )
        return 1
    subprocess.run(kubectl + ["delete", "job", name, "--wait=true"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
