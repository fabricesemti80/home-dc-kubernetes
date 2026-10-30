#!/usr/bin/env python3
"""Capture Immich's scoped original tree; a seed is not an accepted paused recovery set."""
import argparse
import datetime as dt
import json
import hashlib
from pathlib import PurePosixPath
import re
import urllib.request
import uuid
from pathlib import Path
import subprocess

from backup_apps import (CONTAINER_SECURITY, PYTHON_IMAGE, ROOT, RUNTIME, SECURITY,
                         SOURCES, Resources, backend, doppler, keychain, source_pod)
from backup_apps import postgres_restore, recovery_reader, unpack
from backup_transport import port_forward

PHOTO_SOURCE = {"cluster": "app-cluster", "namespace": "media", "profile": "photos-daily"}
DB_SOURCE = SOURCES["immich-db"]
MOUNTPOINT = ".backup-metadata"


def prepare():
    resources = Resources("app-cluster", "media")
    script = """import json,pathlib
p=pathlib.Path('/photos/.backup-metadata')
if p.is_symlink():raise RuntimeError('Metadata mountpoint must not be a symlink')
if p.exists():
 if not p.is_dir() or any(p.iterdir()):raise RuntimeError('Existing metadata mountpoint is not empty; refusing modification')
else:p.mkdir(mode=0o755)
print(json.dumps({'empty_metadata_mountpoint_ready':True,'original_files_modified':False}))
"""
    try:
        resources.create({"apiVersion": "v1", "kind": "Pod", "metadata": {"name": resources.name}, "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False, "securityContext": {**SECURITY, "runAsUser": 1000, "runAsGroup": 1000}, "containers": [{"name": "prepare", "image": PYTHON_IMAGE, "command": ["python3", "-c", script], "securityContext": CONTAINER_SECURITY, "volumeMounts": [{"name": "photos", "mountPath": "/photos"}]}], "volumes": [{"name": "photos", "nfs": {"server": "10.0.40.2", "path": "/media/immich"}}]}})
        resources.call("wait", "--for=jsonpath={.status.containerStatuses[0].state.terminated.exitCode}", "pod/" + resources.name, "--timeout=120s")
        pod = resources.get("pod", resources.name)
        if pod["status"]["containerStatuses"][0]["state"]["terminated"]["exitCode"]:
            raise RuntimeError("Photo metadata mountpoint bootstrap failed; no source permissions changed")
        print(resources.call("logs", resources.name).stdout, end="")
    finally:
        resources.cleanup()


def capture():
    resources = Resources("app-cluster", "media")
    record = None
    try:
        _, image = source_pod(resources, DB_SOURCE)
        password = doppler("apps", "K8UP_MEDIA_PHOTOS_DAILY_PASSWORD")
        if password != keychain(PHOTO_SOURCE):
            raise RuntimeError("Photo repository primary/independent keys differ")
        resources.create({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": resources.name}, "stringData": {"repository-password": password, "source-password": doppler("apps", "IMMICH_BACKUP_PASSWORD")}})
        resources.create({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": resources.name}, "data": {name: (RUNTIME / name).read_text() for name in ["source_inspector.py", "postgres_export.sh", "photo_capture.sh"]}})
        resources.create({"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": resources.name}, "automountServiceAccountToken": False})
        resources.create({"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": {"name": resources.name}, "rules": [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list"]}, {"apiGroups": ["k8up.io"], "resources": ["snapshots"], "verbs": ["get", "list", "create", "update", "patch"]}]})
        resources.create({"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": {"name": resources.name}, "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": resources.name}, "subjects": [{"kind": "ServiceAccount", "name": resources.name, "namespace": "media"}]})
        claim = resources.name
        pv = "immich-photo-source-" + resources.run_id
        resources.create({"apiVersion": "v1", "kind": "PersistentVolume", "metadata": {"name": pv}, "spec": {"capacity": {"storage": "8Ti"}, "accessModes": ["ReadOnlyMany"], "storageClassName": "", "persistentVolumeReclaimPolicy": "Retain", "claimRef": {"name": claim, "namespace": "media"}, "nfs": {"server": "10.0.40.2", "path": "/media/immich", "readOnly": True}}})
        labels = {"backup.krapulax.dev/app": "immich-photos", "backup.krapulax.dev/policy": "photos-daily", "backup.krapulax.dev/operation": resources.run_id}
        resources.create({"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": claim, "labels": dict(labels), "annotations": {"k8up.io/backup": "true"}}, "spec": {"accessModes": ["ReadOnlyMany"], "storageClassName": "", "volumeName": pv, "resources": {"requests": {"storage": "100Gi"}}}})
        volumes = [{"name": "repository", "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"}}, {"name": "tmp", "emptyDir": {}}, {"name": "metadata", "emptyDir": {"medium": "Memory", "sizeLimit": "512Mi"}}, {"name": "scripts", "configMap": {"name": resources.name}}, {"name": "recovery", "secret": {"secretName": "immich-secrets", "defaultMode": 288}}, {"name": "api", "projected": {"defaultMode": 288, "sources": [{"serviceAccountToken": {"path": "token", "expirationSeconds": 600}}, {"configMap": {"name": "kube-root-ca.crt", "items": [{"key": "ca.crt", "path": "ca.crt"}]}}]}}]
        metadata_mounts = [{"name": "metadata", "mountPath": "/stage"}, {"name": "scripts", "mountPath": "/scripts", "readOnly": True}]
        inspector = {"name": "inspect", "image": PYTHON_IMAGE, "command": ["python3", "/scripts/source_inspector.py"], "env": [{"name": "POD_NAMESPACE", "value": "media"}, {"name": "BACKUP_CLUSTER", "value": "app-cluster"}, {"name": "BACKUP_APP", "value": "immich-db"}, {"name": "SOURCE_SELECTOR", "value": DB_SOURCE["selector"]}, {"name": "SOURCE_CONTAINER", "value": "app"}], "securityContext": CONTAINER_SECURITY, "volumeMounts": metadata_mounts + [{"name": "api", "mountPath": "/var/run/backup-api", "readOnly": True}]}
        capture_init = {"name": "capture-database", "image": image, "command": ["sh", "/scripts/photo_capture.sh"], "env": [{"name": "PGUSER", "value": "k8up_backup"}, {"name": "PGDATABASE", "value": "immich"}, {"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": resources.name, "key": "source-password"}}}, {"name": "PGOPTIONS", "value": "-c default_transaction_read_only=on"}], "securityContext": CONTAINER_SECURITY, "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "2", "memory": "768Mi"}}, "volumeMounts": metadata_mounts + [{"name": "recovery", "mountPath": "/recovery-secrets/immich-secrets", "readOnly": True}]}
        pod_spec = {"serviceAccountName": resources.name, "automountServiceAccountToken": True, "securityContext": {**SECURITY, "fsGroup": 1004}, "initContainers": [inspector, capture_init], "containers": [{"name": "k8up", "securityContext": CONTAINER_SECURITY, "env": [{"name": "RESTIC_ONE_FILESYSTEM", "value": "false"}], "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}, {"name": "metadata", "mountPath": f"/data/{claim}/{MOUNTPOINT}"}]}], "volumes": volumes}
        resources.create({"apiVersion": "k8up.io/v1", "kind": "PodConfig", "metadata": {"name": resources.name}, "spec": {"template": {"spec": pod_spec}}})
        operation = resources.create({"apiVersion": "k8up.io/v1", "kind": "Backup", "metadata": {"name": resources.name, "labels": dict(labels)}, "spec": {"backend": backend(PHOTO_SOURCE, resources.name), "clusterName": "app-cluster", "podConfigRef": {"name": resources.name}, "activeDeadlineSeconds": 10800, "successfulJobsHistoryLimit": 24, "failedJobsHistoryLimit": 12, "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "2", "memory": "2Gi"}}, "labelSelectors": [{"matchLabels": labels}]}}, retain=True)
        print(json.dumps({"phase": "seeding", "backup": resources.name, "source_read_only": True, "matched_recovery_set": False}), flush=True)
        resources.call("wait", "--for=jsonpath={.status.finished}=true", "backups.k8up.io/" + resources.name, "--timeout=11000s", timeout=11100)
        completed = resources.get("backups.k8up.io", resources.name)
        if not any(c["type"] == "Completed" and c["status"] == "True" and c.get("reason") == "Succeeded" for c in completed.get("status", {}).get("conditions", [])):
            raise RuntimeError("Photo seed failed; no recovery set accepted")
        path = "/data/" + claim
        snapshots = [s["spec"] for s in resources.get("snapshots.k8up.io")["items"] if s["spec"].get("paths") == [path] and s["spec"].get("repository") == backend(PHOTO_SOURCE, resources.name)["local"]["mountPath"] and s["spec"]["date"] >= operation["metadata"]["creationTimestamp"]]
        if not snapshots:
            raise RuntimeError("Successful seed lacks its fresh exact-path snapshot")
        snapshot = max(snapshots, key=lambda item: item["date"])
        record = {"app": "immich-photos", "cluster": "app-cluster", "namespace": "media", "profile": "photos-daily", "snapshot": snapshot["id"], "date": snapshot["date"], "path": path, "backup_uid": operation["metadata"]["uid"], "seed_only": True, "matched_recovery_set": False}
        directory = ROOT / ".private/backup-captures"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = directory / ("immich-photos-" + snapshot["id"] + ".json")
        output.write_text(json.dumps(record, sort_keys=True) + "\n")
        output.chmod(0o600)
        print(json.dumps(record), flush=True)
        return record
    finally:
        if record is None:
            resources.call("delete", "backups.k8up.io", resources.name, "--ignore-not-found", "--cascade=foreground", "--wait=true", check=False)
        else:
            jobs = resources.get("jobs")["items"]
            job_uids = {job["metadata"]["uid"] for job in jobs if any(owner["uid"] == operation["metadata"]["uid"] for owner in job["metadata"].get("ownerReferences", []))}
            for pod in resources.get("pods")["items"]:
                if pod["status"]["phase"] in {"Succeeded", "Failed"} and any(owner["uid"] in job_uids for owner in pod["metadata"].get("ownerReferences", [])):
                    resources.call("delete", "pod", pod["metadata"]["name"], "--wait=true")
        resources.cleanup()


def verify(snapshot):
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        raise RuntimeError("Photo restore requires a full immutable snapshot ID")
    namespace = "backup-restore-immich-photos-" + uuid.uuid4().hex[:8]
    resources = Resources("app-cluster", namespace, own_namespace=True)
    scratch = "/repository/app-cluster/media/.restore-photos-" + resources.run_id
    reader_ready = False
    try:
        resources.create({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace, "labels": {"pod-security.kubernetes.io/enforce": "baseline"}}})
        resources.create({"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": {"name": "no-outbound-integrations"}, "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"], "ingress": [], "egress": []}})
        recovery_reader(resources, PHOTO_SOURCE, keychain(PHOTO_SOURCE), inspect_restored_files=True)
        reader_ready = True
        snapshots = json.loads(resources.call("exec", "repository", "-c", "restic", "--", "restic", "snapshots", "--json", snapshot).stdout)
        if len(snapshots) != 1 or snapshots[0]["id"] != snapshot or len(snapshots[0]["paths"]) != 1:
            raise RuntimeError("Photo snapshot identity/path is ambiguous")
        path = PurePosixPath(snapshots[0]["paths"][0])
        if not path.is_absolute() or path.parts[:2] != ("/", "data") or len(path.parts) != 3 or ".." in path.parts:
            raise RuntimeError("Photo snapshot has an unexpected source root")
        resources.call("exec", "repository", "-c", "restic", "--", "restic", "check", "--read-data", timeout=10800)
        resources.call("exec", "repository", "-c", "restic", "--", "sh", "-ec", 'umask 077; test ! -e "$1"; mkdir -m 700 "$1"; restic restore "$2" --target "$1" --verify', "--", scratch, snapshot, timeout=10800)
        root = scratch + str(path)
        proof = json.loads(resources.call("exec", "repository", "-c", "transfer", "--", "python3", "-c", (RUNTIME / "photo_verify.py").read_text(), root, timeout=10800).stdout)
        remote_hash = resources.call("exec", "repository", "-c", "restic", "--", "sh", "-ec", 'cp "$1/.backup-metadata/database.tar" /work/bundle.tar; sha256sum /work/bundle.tar', "--", root).stdout.split()[0]
        with port_forward(resources, "repository", 8080) as address:
            with urllib.request.urlopen(address + "/bundle.tar", timeout=120) as response:
                archive = response.read(512 * 1024 * 1024 + 1)
                if len(archive) != int(response.headers["Content-Length"]) or len(archive) > 512 * 1024 * 1024:
                    raise RuntimeError("Photo database transfer exceeds its exact staging bound")
        if hashlib.sha256(archive).hexdigest() != remote_hash:
            raise RuntimeError("Photo database transfer checksum differs")
        files, metadata = unpack(archive, "immich-db", DB_SOURCE)
        database_proof = postgres_restore(resources, DB_SOURCE, files, metadata)
        database = json.loads(files["database.json"])["database"]
        query = "SELECT json_build_object('path',\"originalPath\",'sha1',encode(checksum,'hex')) FROM asset ORDER BY id;"
        result = resources.call("exec", "database", "-c", "postgres", "--", "sh", "-ec", 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -h 127.0.0.1 -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -Atc "$2"', "--", database, query).stdout
        references = [json.loads(line) for line in result.splitlines()]
        recovered_hash = hashlib.sha256(json.dumps(references, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if recovered_hash != proof["canonical_reference_sha256"] or len(references) != proof["referenced_assets"]:
            raise RuntimeError("Restored database and original-file manifest do not describe the same assets")
        record = {"app": "immich-photos", "snapshot": snapshot, "profile": "photos-daily", "restored": True, "matched_recovery_set": False, "production_cutover": False, "database": database_proof, "originals": proof, "verified_at": dt.datetime.now(dt.UTC).isoformat()}
        directory = ROOT / ".private/backup-restores"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = directory / ("immich-photos-" + snapshot + ".json")
        output.write_text(json.dumps(record, sort_keys=True) + "\n")
        output.chmod(0o600)
        print(json.dumps(record), flush=True)
        return record
    finally:
        try:
            if reader_ready:
                resources.call("exec", "repository", "-c", "restic", "--", "sh", "-ec", 'case "$1" in /repository/app-cluster/media/.restore-photos-*) rm -rf -- "$1";; *) exit 1;; esac', "--", scratch)
        finally:
            resources.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "seed", "verify"])
    parser.add_argument("--snapshot")
    args = parser.parse_args()
    try:
        if args.action == "verify":
            if not args.snapshot:
                parser.error("verify requires --snapshot with a full immutable ID")
            verify(args.snapshot)
        elif args.action == "prepare":
            prepare()
        else:
            capture()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
