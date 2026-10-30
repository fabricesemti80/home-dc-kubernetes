#!/usr/bin/env python3
"""Exercise K8up using disposable files only; never enroll production sources."""

import argparse
import hashlib
import secrets
import sys
from k8up_pilot import CONTAINER_SECURITY, SECURITY, TARGETS, Pilot, run


class FilePilot(Pilot):

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=TARGETS)
    args = parser.parse_args()
    return run(FilePilot(args.cluster))


if __name__ == "__main__":
    sys.exit(main())
