#!/usr/bin/env python3
"""Exercise K8up using disposable files only; never enroll production sources."""

import argparse
import hashlib
import json
import secrets
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
    def __init__(self, cluster):
        kubeconfig, self.nodes = TARGETS[cluster]
        self.kubectl = ["kubectl", "--kubeconfig", str(kubeconfig)]
        self.namespace = f"backup-file-pilot-{uuid.uuid4().hex[:8]}"
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

    def pvc(self, name, enabled):
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
                    "resources": {"requests": {"storage": "32Mi"}},
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

    def execute(self):
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": self.namespace,
                    "labels": {"pod-security.kubernetes.io/enforce": "baseline"},
                },
            }
        )
        self.created = True
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "pilot-repository"},
                "stringData": {"password": secrets.token_urlsafe(48)},
            }
        )
        backend = {
            "local": {"mountPath": f"/repository/{self.repository}"},
            "repoPasswordSecretRef": {"name": "pilot-repository", "key": "password"},
            "volumeMounts": [{"name": "repository", "mountPath": "/repository"}],
        }
        for name, node in [("pilot-runner", None), ("restore-runner", self.nodes[0])]:
            spec = {
                "securityContext": SECURITY,
                "containers": [
                    {
                        "name": "k8up",
                        "securityContext": CONTAINER_SECURITY,
                        "env": [{"name": "RESTIC_CACHE_DIR", "value": "/k8up/cache"}],
                        "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                    }
                ],
                "volumes": [
                    {
                        "name": "repository",
                        "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"},
                    },
                    {"name": "tmp", "emptyDir": {}},
                ],
            }
            if node:
                spec["nodeSelector"] = {"kubernetes.io/hostname": node}
                spec["tolerations"] = [
                    {
                        "key": "node-role.kubernetes.io/control-plane",
                        "operator": "Exists",
                        "effect": "NoSchedule",
                    }
                ]
            self.create(
                {
                    "apiVersion": "k8up.io/v1",
                    "kind": "PodConfig",
                    "metadata": {"name": name},
                    "spec": {"template": {"spec": spec}},
                }
            )
        payloads = {
            name: secrets.token_hex(4096)
            for name in ("source-a", "source-b", "excluded")
        }
        for name, node in [
            ("source-a", self.nodes[0]),
            ("source-b", self.nodes[1]),
            ("excluded", self.nodes[0]),
        ]:
            self.pvc(name, name != "excluded")
            self.pod(
                name,
                node,
                [{"name": "data", "persistentVolumeClaim": {"claimName": name}}],
                [{"name": "data", "mountPath": "/data"}],
                'printf "%s" "$PAYLOAD" > /data/probe; exec sleep 3600',
                [{"name": "PAYLOAD", "value": payloads[name]}],
                True,
            )
            self.command(
                "wait",
                "--for=condition=Ready",
                f"pod/{name}",
                "--timeout=180s",
                capture_output=True,
            )
        self.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "Backup",
                "metadata": {"name": "files"},
                "spec": {
                    "backend": backend,
                    "podConfigRef": {"name": "pilot-runner"},
                    "activeDeadlineSeconds": 240,
                    "resources": {
                        "requests": {"cpu": "50m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "1Gi"},
                    },
                    "labelSelectors": [
                        {"matchLabels": {"backup.krapulax.dev/policy": "pilot-files"}}
                    ],
                },
            }
        )
        backup = self.wait_operation("backups.k8up.io", "files")
        jobs = [
            j
            for j in self.get("jobs")["items"]
            if any(
                o["uid"] == backup["metadata"]["uid"]
                for o in j["metadata"].get("ownerReferences", [])
            )
        ]
        if {
            j["spec"]["template"]["spec"]
            .get("nodeSelector", {})
            .get("kubernetes.io/hostname")
            for j in jobs
        } != set(self.nodes):
            raise RuntimeError("Backup Jobs did not follow both source workers")
        if any(
            j["spec"]["template"]["spec"].get("securityContext", {}).get("runAsUser")
            != 1004
            for j in jobs
        ):
            raise RuntimeError(
                "Backup Jobs did not retain the non-root writer identity"
            )
        snapshots = self.get("snapshots.k8up.io")["items"]
        paths = {p for snapshot in snapshots for p in snapshot["spec"].get("paths", [])}
        if paths != {"/data/source-a", "/data/source-b"}:
            raise RuntimeError(
                f"Unexpected source coverage (including exclusion check): {paths}"
            )
        snapshot = next(s for s in snapshots if "/data/source-b" in s["spec"]["paths"])
        self.pvc("restored", False)
        self.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "Restore",
                "metadata": {"name": "files"},
                "spec": {
                    "backend": backend,
                    "podConfigRef": {"name": "restore-runner"},
                    "snapshot": snapshot["spec"]["id"],
                    "paths": ["/data/source-b"],
                    "restoreMethod": {"folder": {"claimName": "restored"}},
                    "activeDeadlineSeconds": 240,
                },
            }
        )
        self.wait_operation("restores.k8up.io", "files")
        self.pod(
            "verify",
            self.nodes[0],
            [{"name": "data", "persistentVolumeClaim": {"claimName": "restored"}}],
            [{"name": "data", "mountPath": "/data"}],
            "exec sleep 3600",
        )
        self.command(
            "wait",
            "--for=condition=Ready",
            "pod/verify",
            "--timeout=90s",
            capture_output=True,
        )
        found = self.command(
            "exec",
            "verify",
            "--",
            "find",
            "/data",
            "-type",
            "f",
            "-name",
            "probe",
            capture_output=True,
        ).stdout.splitlines()
        if len(found) != 1:
            raise RuntimeError(
                f"Restore did not contain exactly the selected source file: {found}"
            )
        actual = self.command(
            "exec", "verify", "--", "sha256sum", found[0], capture_output=True
        ).stdout.split()[0]
        expected = hashlib.sha256(payloads["source-b"].encode()).hexdigest()
        if actual != expected:
            raise RuntimeError("Restored payload differs from source-b")
        print(
            f"PASS {self.namespace}: two-node non-root backup, excluded PVC omitted, exact source-b snapshot restored to fresh storage on {self.nodes[0]}, SHA-256 matches"
        )

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=TARGETS)
    args = parser.parse_args()
    pilot = Pilot(args.cluster)
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


if __name__ == "__main__":
    sys.exit(main())
