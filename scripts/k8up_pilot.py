"""Shared Kubernetes operations and scoped cleanup for disposable K8up pilots."""

import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "app-cluster": (ROOT / "kubeconfig", ["k8s-wrkr-02", "k8s-wrkr-03"]),
    "infra-cluster": (
        ROOT / ".private/infra-cluster/kubeconfig",
        ["infra-cp-01", "infra-wk-01"],
    ),
}
SECURITY = {
    "runAsNonRoot": True,
    "runAsUser": 1004,
    "runAsGroup": 65534,
    "supplementalGroups": [],
}
CONTAINER_SECURITY = {
    "allowPrivilegeEscalation": False,
    "readOnlyRootFilesystem": True,
    "capabilities": {"drop": ["ALL"]},
    "seccompProfile": {"type": "RuntimeDefault"},
}


class Pilot:
    """Own a unique synthetic namespace and its disposable repository/storage."""

    def __init__(self, cluster, kind="file"):
        kubeconfig, self.nodes = TARGETS[cluster]
        self.kubectl = ["kubectl", "--kubeconfig", str(kubeconfig)]
        self.namespace = f"backup-{kind}-pilot-{uuid.uuid4().hex[:8]}"
        self.repository = f"{cluster}/.{self.namespace}"
        self.created = False

    def command(self, *args, **kwargs):
        return subprocess.run(
            self.kubectl + ["-n", self.namespace, *args],
            check=True,
            text=True,
            **kwargs,
        )

    def get(self, kind, name=None):
        return json.loads(
            self.command(
                "get",
                kind,
                *([name] if name else []),
                "-o",
                "json",
                capture_output=True,
            ).stdout
        )

    def create(self, obj):
        self.command("create", "-f", "-", input=json.dumps(obj), capture_output=True)

    def pvc(self, name, enabled, size="32Mi"):
        self.create(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": name,
                    "annotations": {"k8up.io/backup": str(enabled).lower()},
                    "labels": {"backup.krapulax.dev/policy": "pilot-files"},
                },
                "spec": {
                    "storageClassName": "local-path",
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": size}},
                },
            }
        )

    def pod(self, name, node, volumes, mounts, command, env=None, ready_file=False):
        container = {
            "name": "check",
            "image": "busybox:1.38@sha256:a46257e06c82ad85242d0d38077d0a52d9896389ca60a1a59d3463db586e5fa4",
            "command": ["sh", "-ec", command],
            "env": env or [],
            "volumeMounts": mounts,
            "securityContext": CONTAINER_SECURITY,
            "resources": {
                "requests": {"cpu": "10m", "memory": "16Mi"},
                "limits": {"cpu": "100m", "memory": "32Mi"},
            },
        }
        if ready_file:
            container["readinessProbe"] = {
                "exec": {"command": ["test", "-f", "/data/probe"]},
                "periodSeconds": 2,
            }
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": name},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": SECURITY,
                    "nodeSelector": {"kubernetes.io/hostname": node},
                    "tolerations": [
                        {
                            "key": "node-role.kubernetes.io/control-plane",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        }
                    ],
                    "containers": [container],
                    "volumes": volumes,
                },
            }
        )

    def wait_operation(self, kind, name):
        self.command(
            "wait",
            "--for=jsonpath={.status.finished}=true",
            f"{kind}/{name}",
            "--timeout=300s",
            capture_output=True,
        )
        obj = self.get(kind, name)
        conditions = obj.get("status", {}).get("conditions", [])
        if not any(
            c["type"] == "Completed"
            and c["status"] == "True"
            and c["reason"] == "Succeeded"
            for c in conditions
        ):
            raise RuntimeError(f"{kind}/{name} did not succeed: {conditions}")
        return obj

    def cleanup(self):
        if not self.created:
            return
        claims = self.get("pvc")["items"]
        volumes = [
            p["spec"]["volumeName"] for p in claims if p["spec"].get("volumeName")
        ]
        self.command(
            "delete",
            "backups.k8up.io,restores.k8up.io",
            "--all",
            "--wait=true",
            capture_output=True,
        )
        self.command(
            "delete",
            "jobs",
            "--all",
            "--cascade=foreground",
            "--wait=true",
            "--timeout=120s",
            capture_output=True,
        )
        self.command(
            "delete",
            "pods",
            "--all",
            "--wait=true",
            "--timeout=90s",
            capture_output=True,
        )
        for claim in claims:
            name = claim["metadata"]["name"]
            if claim["spec"].get("volumeName"):
                node = self.nodes[1] if name == "source-b" else self.nodes[0]
                pod = f"cleanup-{name}"
                self.pod(
                    pod,
                    node,
                    [{"name": "data", "persistentVolumeClaim": {"claimName": name}}],
                    [{"name": "data", "mountPath": "/data"}],
                    "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} \\;",
                )
                self.command(
                    "wait",
                    "--for=jsonpath={.status.phase}=Succeeded",
                    f"pod/{pod}",
                    "--timeout=90s",
                    capture_output=True,
                )
        self.pod(
            "repository-cleanup",
            self.nodes[0],
            [
                {
                    "name": "repository",
                    "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"},
                }
            ],
            [{"name": "repository", "mountPath": "/repository"}],
            'rm -rf "/repository/$PILOT_REPOSITORY"',
            [{"name": "PILOT_REPOSITORY", "value": self.repository}],
        )
        self.command(
            "wait",
            "--for=jsonpath={.status.phase}=Succeeded",
            "pod/repository-cleanup",
            "--timeout=90s",
            capture_output=True,
        )
        self.command(
            "delete",
            "namespace",
            self.namespace,
            "--wait=true",
            "--timeout=120s",
            capture_output=True,
        )
        for volume in volumes:
            pv = json.loads(
                subprocess.run(
                    self.kubectl + ["get", "pv", volume, "-o", "json"],
                    check=True,
                    text=True,
                    capture_output=True,
                ).stdout
            )
            if (
                pv["spec"]["claimRef"]["namespace"] != self.namespace
                or pv["spec"]["persistentVolumeReclaimPolicy"] != "Retain"
            ):
                raise RuntimeError(f"Refusing unexpected pilot PV cleanup: {volume}")
            subprocess.run(
                self.kubectl + ["delete", "pv", volume, "--wait=true"],
                check=True,
                text=True,
                capture_output=True,
            )
        print(
            f"Cleaned disposable namespace/repository/PV objects: {self.namespace}; empty Retain backing directories may remain"
        )


def run(pilot):
    print(f"Synthetic-only pilot namespace: {pilot.namespace}", flush=True)
    try:
        pilot.execute()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        for pod in pilot.get("pods").get("items", []) if pilot.created else []:
            name = pod["metadata"]["name"]
            print(f"{name}: {json.dumps(pod.get('status', {}))}", file=sys.stderr)
            result = subprocess.run(
                pilot.kubectl
                + ["-n", pilot.namespace, "logs", name, "--all-containers=true"],
                text=True,
                capture_output=True,
            )
            print(result.stdout, result.stderr, file=sys.stderr)
        if pilot.created:
            events = pilot.command("get", "events", "-o", "wide", capture_output=True)
            print(events.stdout, file=sys.stderr)
        return 1
    finally:
        pilot.cleanup()
    return 0
