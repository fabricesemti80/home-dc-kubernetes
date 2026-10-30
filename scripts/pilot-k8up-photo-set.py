#!/usr/bin/env python3
"""Prove a read-only file tree and private init metadata share one native snapshot."""
import argparse
import base64
import hashlib
import json
import secrets

from k8up_pilot import CONTAINER_SECURITY, SECURITY, TARGETS, Pilot, run


class PhotoSetPilot(Pilot):
    def __init__(self, cluster):
        super().__init__(cluster, kind="photo-set")

    def execute(self):
        self.create({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": self.namespace, "labels": {"pod-security.kubernetes.io/enforce": "baseline"}}})
        self.created = True
        self.create({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "pilot-repository"}, "stringData": {"password": secrets.token_urlsafe(48)}})
        backend = {"local": {"mountPath": f"/repository/{self.repository}"}, "repoPasswordSecretRef": {"name": "pilot-repository", "key": "password"}, "volumeMounts": [{"name": "repository", "mountPath": "/repository"}]}
        payload = bytes(range(256)) * 128
        metadata = json.dumps({"set": secrets.token_hex(16), "purpose": "synthetic-recovery-metadata"})
        self.pvc("source-b", True)
        self.pod("source-b", self.nodes[1], [{"name": "data", "persistentVolumeClaim": {"claimName": "source-b"}}], [{"name": "data", "mountPath": "/data"}], 'mkdir -p /data/.backup-metadata; printf "%s" "$PAYLOAD" | base64 -d > /data/probe; exec sleep 3600', [{"name": "PAYLOAD", "value": base64.b64encode(payload).decode()}], True)
        self.command("wait", "--for=condition=Ready", "pod/source-b", "--timeout=180s", capture_output=True)
        runner = {"securityContext": {**SECURITY, "fsGroup": 1004}, "initContainers": [{"name": "metadata", "image": "busybox:1.38@sha256:a46257e06c82ad85242d0d38077d0a52d9896389ca60a1a59d3463db586e5fa4", "command": ["sh", "-ec", 'umask 077; printf "%s" "$METADATA" > /stage/record.json'], "env": [{"name": "METADATA", "value": metadata}], "securityContext": CONTAINER_SECURITY, "volumeMounts": [{"name": "metadata", "mountPath": "/stage"}]}], "containers": [{"name": "k8up", "securityContext": CONTAINER_SECURITY, "volumeMounts": [{"name": "metadata", "mountPath": "/data/source-b/.backup-metadata"}, {"name": "tmp", "mountPath": "/tmp"}]}], "volumes": [{"name": "metadata", "emptyDir": {"medium": "Memory", "sizeLimit": "16Mi"}}, {"name": "repository", "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"}}, {"name": "tmp", "emptyDir": {}}]}
        self.create({"apiVersion": "k8up.io/v1", "kind": "PodConfig", "metadata": {"name": "capture"}, "spec": {"template": {"spec": runner}}})
        restore_runner = {"securityContext": SECURITY, "nodeSelector": {"kubernetes.io/hostname": self.nodes[0]}, "tolerations": [{"key": "node-role.kubernetes.io/control-plane", "operator": "Exists", "effect": "NoSchedule"}], "containers": [{"name": "k8up", "securityContext": CONTAINER_SECURITY, "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}]}], "volumes": [{"name": "repository", "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"}}, {"name": "tmp", "emptyDir": {}}]}
        self.create({"apiVersion": "k8up.io/v1", "kind": "PodConfig", "metadata": {"name": "restore"}, "spec": {"template": {"spec": restore_runner}}})
        self.create({"apiVersion": "k8up.io/v1", "kind": "Backup", "metadata": {"name": "photo-set"}, "spec": {"backend": backend, "podConfigRef": {"name": "capture"}, "activeDeadlineSeconds": 240, "labelSelectors": [{"matchLabels": {"backup.krapulax.dev/policy": "pilot-files"}}]}})
        self.wait_operation("backups.k8up.io", "photo-set")
        snapshots = self.get("snapshots.k8up.io")["items"]
        if len(snapshots) != 1 or snapshots[0]["spec"]["paths"] != ["/data/source-b"]:
            raise RuntimeError("Metadata and original tree did not produce exactly one stable-path snapshot")
        self.command("exec", "source-b", "--", "test", "!", "-e", "/data/.backup-metadata/record.json", capture_output=True)
        self.pvc("restored", False)
        self.create({"apiVersion": "k8up.io/v1", "kind": "Restore", "metadata": {"name": "photo-set"}, "spec": {"backend": backend, "podConfigRef": {"name": "restore"}, "snapshot": snapshots[0]["spec"]["id"], "paths": ["/data/source-b"], "restoreMethod": {"folder": {"claimName": "restored"}}, "activeDeadlineSeconds": 240}})
        self.wait_operation("restores.k8up.io", "photo-set")
        self.pod("verify", self.nodes[0], [{"name": "data", "persistentVolumeClaim": {"claimName": "restored"}}], [{"name": "data", "mountPath": "/data"}], "exec sleep 3600")
        self.command("wait", "--for=condition=Ready", "pod/verify", "--timeout=90s", capture_output=True)
        for leaf, expected in [("probe", hashlib.sha256(payload).hexdigest()), ("record.json", hashlib.sha256(metadata.encode()).hexdigest())]:
            files = self.command("exec", "verify", "--", "find", "/data", "-type", "f", "-name", leaf, capture_output=True).stdout.splitlines()
            if len(files) != 1:
                raise RuntimeError("Restored recovery set lost or duplicated one required member")
            actual = self.command("exec", "verify", "--", "sha256sum", files[0], capture_output=True).stdout.split()[0]
            if actual != expected:
                raise RuntimeError("Restored recovery-set member checksum differs")
        print(json.dumps({"cluster": self.nodes, "single_snapshot": True, "private_metadata_restored": True, "binary_original_restored": True, "source_metadata_not_written": True, "cross_worker_restore": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=TARGETS)
    args = parser.parse_args()
    return run(PhotoSetPilot(args.cluster))


if __name__ == "__main__":
    raise SystemExit(main())
