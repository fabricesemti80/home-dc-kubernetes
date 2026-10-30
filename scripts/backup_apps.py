#!/usr/bin/env python3
"""Capture real app state with K8up; restore only into a fresh isolated namespace."""

import argparse
import base64
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tarfile
import uuid
import urllib.request

from k8up_pilot import CONTAINER_SECURITY, SECURITY, TARGETS
from backup_transport import port_forward

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "kubernetes/components/backup-runtime"
SOURCES = json.loads((RUNTIME / "sources.json").read_text())
PYTHON_IMAGE = "python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b"
RESTIC_IMAGE = "restic/restic:0.19.1@sha256:136600b6ff6843d61d355f7f71f460a166429f35de6fd11b568fece3c9a4d510"


def doppler(config, key):
    result = subprocess.run(
        [
            "doppler",
            "secrets",
            "get",
            key,
            "--project",
            "home-dc-kubernetes",
            "--config",
            config,
            "--json",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(
            f"Cannot retrieve required Doppler item {config}/{key}; credential output suppressed"
        )
    return json.loads(result.stdout)[key]["computed"]


def keychain(source):
    service = (
        f"home-dc.backups.{source['cluster']}.{source['namespace']}.{source['profile']}"
    )
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            "restic",
            "-s",
            service,
            "-w",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if result.returncode or not result.stdout.removesuffix("\n"):
        raise RuntimeError(
            f"Independent recovery key unavailable: Keychain service {service}, account restic"
        )
    return result.stdout.removesuffix("\n")


def backend(source, secret):
    return {
        "local": {
            "mountPath": f"/repository/{source['cluster']}/{source['namespace']}/{source['profile']}"
        },
        "repoPasswordSecretRef": {"name": secret, "key": "repository-password"},
        "volumeMounts": [{"name": "repository", "mountPath": "/repository"}],
    }


def qident(value):
    return '"' + value.replace('"', '""') + '"'


class Resources:
    def __init__(self, cluster, namespace, own_namespace=False):
        self.cluster = cluster
        self.namespace = namespace
        self.kubectl = ["kubectl", "--kubeconfig", str(TARGETS[cluster][0])]
        self.run_id = uuid.uuid4().hex[:12]
        self.name = "backup-proof-" + self.run_id
        self.owned = []
        self.own_namespace = own_namespace
        self.namespace_created = False

    def call(self, *args, value=None, binary=False, check=True, timeout=1000):
        result = subprocess.run(
            self.kubectl + ["-n", self.namespace, *args],
            input=value,
            text=not binary,
            capture_output=True,
            timeout=timeout,
        )
        if check and result.returncode:
            if args[0] == "exec":
                directory = ROOT / ".private/backup-diagnostics"
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                diagnostic = directory / f"{self.run_id}.log"
                message = (
                    result.stderr.decode(errors="replace") if binary else result.stderr
                )
                diagnostic.write_text(message)
                diagnostic.chmod(0o600)
                raise RuntimeError(
                    f"Recovery command failed; private diagnostic: {diagnostic}"
                )
            raise RuntimeError(
                f"Kubernetes operation failed: {args[0]}; credential-bearing diagnostics suppressed"
            )
        return result

    def get(self, kind, name=None):
        return json.loads(
            self.call("get", kind, *([name] if name else []), "-o", "json").stdout
        )

    def create(self, obj, retain=False):
        obj.setdefault("metadata", {}).setdefault("labels", {})[
            "backup.krapulax.dev/proof-id"
        ] = self.run_id
        response = json.loads(
            self.call("create", "-f", "-", "-o", "json", value=json.dumps(obj)).stdout
        )
        if obj["kind"] == "Namespace":
            self.namespace_created = True
        elif not retain:
            self.owned.append(
                (obj["kind"], response["metadata"]["name"], response["metadata"]["uid"])
            )
        return response

    def cleanup(self):
        if self.own_namespace:
            if not self.namespace_created:
                return
            claims = self.get("pvc")["items"]
            self.call("delete", "pods", "--all", "--wait=true", "--timeout=120s")
            # Erase only the fresh recovery PVC using its own node/claim binding.
            for claim in claims:
                if not claim["spec"].get("volumeName"):
                    continue
                name = "erase-" + claim["metadata"]["name"]
                self.create(
                    {
                        "apiVersion": "v1",
                        "kind": "Pod",
                        "metadata": {"name": name},
                        "spec": {
                            "restartPolicy": "Never",
                            "automountServiceAccountToken": False,
                            "securityContext": SECURITY,
                            "containers": [
                                {
                                    "name": "erase",
                                    "image": PYTHON_IMAGE,
                                    "command": [
                                        "python3",
                                        "-c",
                                        "import pathlib,shutil; p=pathlib.Path('/data'); [(shutil.rmtree(x) if x.is_dir() and not x.is_symlink() else x.unlink()) for x in p.iterdir()]",
                                    ],
                                    "securityContext": CONTAINER_SECURITY,
                                    "volumeMounts": [
                                        {"name": "data", "mountPath": "/data"}
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "data",
                                    "persistentVolumeClaim": {
                                        "claimName": claim["metadata"]["name"]
                                    },
                                }
                            ],
                        },
                    }
                )
                self.call(
                    "wait",
                    "--for=jsonpath={.status.phase}=Succeeded",
                    "pod/" + name,
                    "--timeout=120s",
                )
            volumes = [
                c["spec"]["volumeName"] for c in claims if c["spec"].get("volumeName")
            ]
            self.call(
                "delete", "namespace", self.namespace, "--wait=true", "--timeout=180s"
            )
            for volume in volumes:
                pv = self.get("pv", volume)
                if (
                    pv["spec"]["claimRef"]["namespace"] != self.namespace
                    or pv["spec"]["persistentVolumeReclaimPolicy"] != "Retain"
                ):
                    raise RuntimeError("Refusing unexpected recovery PV cleanup")
                self.call("delete", "pv", volume, "--wait=true")
        else:
            for kind, name, uid in reversed(self.owned):
                result = self.call("get", kind, name, "-o", "json", check=False)
                if result.returncode:
                    continue
                obj = json.loads(result.stdout)
                if (
                    obj["metadata"]["uid"] != uid
                    or obj["metadata"]
                    .get("labels", {})
                    .get("backup.krapulax.dev/proof-id")
                    != self.run_id
                ):
                    raise RuntimeError(
                        "Refusing cleanup of a resource not owned by this proof"
                    )
                self.call(
                    "delete",
                    kind,
                    name,
                    "--cascade=foreground",
                    "--wait=true",
                    "--timeout=120s",
                )


def source_pod(resources, source):
    pods = resources.get("pods")["items"]
    # Match the exact Kubernetes equality selector; source definitions are reviewed constants.
    labels = dict(part.split("=", 1) for part in source["selector"].split(","))
    ready = [
        p
        for p in pods
        if all(p["metadata"].get("labels", {}).get(k) == v for k, v in labels.items())
        and not p["metadata"].get("deletionTimestamp")
        and any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in p["status"].get("conditions", [])
        )
    ]
    if len(ready) != 1:
        raise RuntimeError("Source selector does not resolve exactly one ready pod")
    pod = ready[0]
    container = next(
        c
        for c in pod["status"]["containerStatuses"]
        if c["name"] == source["container"]
    )
    image = container["imageID"].removeprefix("docker-pullable://")
    if "@sha256:" not in image:
        raise RuntimeError("Source has no pullable immutable image digest")
    return pod, image


def capture(app):
    source = SOURCES[app]
    resources = Resources(source["cluster"], source["namespace"])
    success = False
    backup_name = resources.name
    try:
        _, image = source_pod(resources, source)
        config = "apps" if source["cluster"] == "app-cluster" else "infra"
        password_key = (
            f"K8UP_{source['namespace']}_{source['profile']}_PASSWORD".upper().replace(
                "-", "_"
            )
        )
        repository_password = doppler(config, password_key)
        if repository_password != keychain(source):
            raise RuntimeError(
                "Primary and independent repository keys differ; no capture started"
            )
        credentials = {
            "repository-password": repository_password,
            "source-password": doppler(config, source["backup_password"]),
        }
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": resources.name},
                "stringData": credentials,
            }
        )
        files = ["source_inspector.py", "postgres_export.sh"]
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": resources.name},
                "data": {name: (RUNTIME / name).read_text() for name in files},
            }
        )
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": resources.name},
                "automountServiceAccountToken": False,
            }
        )
        resources.create(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": resources.name},
                "rules": [
                    {"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list"]}
                ],
            }
        )
        resources.create(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": resources.name},
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "Role",
                    "name": resources.name,
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": resources.name,
                        "namespace": source["namespace"],
                    }
                ],
            }
        )
        resources.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "PodConfig",
                "metadata": {"name": resources.name},
                "spec": {
                    "template": {
                        "spec": {
                            "securityContext": SECURITY,
                            "containers": [
                                {
                                    "name": "k8up",
                                    "securityContext": CONTAINER_SECURITY,
                                    "volumeMounts": [
                                        {"name": "tmp", "mountPath": "/tmp"}
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "repository",
                                    "nfs": {
                                        "server": "10.0.40.2",
                                        "path": "/k8s-backup",
                                    },
                                },
                                {"name": "tmp", "emptyDir": {}},
                            ],
                        }
                    }
                },
            }
        )
        volumes = [
            {"name": "scripts", "configMap": {"name": resources.name}},
            {"name": "stage", "emptyDir": {"medium": "Memory", "sizeLimit": "512Mi"}},
            {
                "name": "api",
                "projected": {
                    "defaultMode": 288,
                    "sources": [
                        {
                            "serviceAccountToken": {
                                "path": "token",
                                "expirationSeconds": 600,
                            }
                        },
                        {
                            "configMap": {
                                "name": "kube-root-ca.crt",
                                "items": [{"key": "ca.crt", "path": "ca.crt"}],
                            }
                        },
                    ],
                },
            },
        ]
        mounts = [
            {"name": "scripts", "mountPath": "/scripts", "readOnly": True},
            {"name": "stage", "mountPath": "/stage"},
        ]
        for index, name in enumerate(source["recovery_secrets"]):
            resources.get(
                "secret", name
            )  # Existence check only; never print credentials.
            volumes.append(
                {
                    "name": f"secret-{index}",
                    "secret": {"secretName": name, "defaultMode": 288},
                }
            )
            mounts.append(
                {
                    "name": f"secret-{index}",
                    "mountPath": "/recovery-secrets/" + name,
                    "readOnly": True,
                }
            )
        inspector_env = [
            {
                "name": "POD_NAMESPACE",
                "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}},
            },
            {"name": "SOURCE_SELECTOR", "value": source["selector"]},
            {"name": "SOURCE_CONTAINER", "value": source["container"]},
            {"name": "BACKUP_APP", "value": app},
            {"name": "BACKUP_CLUSTER", "value": source["cluster"]},
        ]
        init = {
            "name": "inspect",
            "image": PYTHON_IMAGE,
            "command": ["python3", "/scripts/source_inspector.py"],
            "env": inspector_env,
            "securityContext": CONTAINER_SECURITY,
            "resources": {
                "requests": {"cpu": "10m", "memory": "32Mi"},
                "limits": {"cpu": "100m", "memory": "64Mi"},
            },
            "volumeMounts": mounts[:2]
            + [{"name": "api", "mountPath": "/var/run/backup-api", "readOnly": True}],
        }
        environment = [
            {"name": "PGUSER", "value": "k8up_backup"},
            {
                "name": "PGPASSWORD",
                "valueFrom": {
                    "secretKeyRef": {"name": resources.name, "key": "source-password"}
                },
            },
            {"name": "PGOPTIONS", "value": "-c default_transaction_read_only=on"},
            {
                "name": "PGDATABASE",
                **(
                    {"value": source["database"]}
                    if "database" in source
                    else {"valueFrom": {"secretKeyRef": source["database_secret"]}}
                ),
            },
        ]
        command = "sh /scripts/postgres_export.sh"
        exporter_image = image
        labels = {
            "backup.krapulax.dev/app": app,
            "backup.krapulax.dev/policy": source["profile"],
            "backup.krapulax.dev/operation": resources.run_id,
        }
        resources.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "PreBackupPod",
                "metadata": {"name": resources.name, "labels": labels},
                "spec": {
                    "backupCommand": command,
                    "fileExtension": ".tar",
                    "pod": {
                        "spec": {
                            "automountServiceAccountToken": False,
                            "serviceAccountName": resources.name,
                            "securityContext": {**SECURITY, "fsGroup": 1004},
                            "initContainers": [init],
                            "containers": [
                                {
                                    "name": app,
                                    "image": exporter_image,
                                    "command": ["sleep", "1800"],
                                    "env": environment,
                                    "securityContext": CONTAINER_SECURITY,
                                    "resources": {
                                        "requests": {"cpu": "100m", "memory": "128Mi"},
                                        "limits": {"cpu": "1", "memory": "768Mi"},
                                    },
                                    "volumeMounts": mounts,
                                }
                            ],
                            "volumes": volumes,
                        }
                    },
                },
            }
        )
        backup = resources.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "Backup",
                "metadata": {"name": backup_name, "labels": labels},
                "spec": {
                    "backend": backend(source, resources.name),
                    "clusterName": source["cluster"],
                    "podConfigRef": {"name": resources.name},
                    "activeDeadlineSeconds": 600,
                    "successfulJobsHistoryLimit": 48,
                    "failedJobsHistoryLimit": 24,
                    "labelSelectors": [{"matchLabels": labels}],
                },
            },
            retain=True,
        )
        resources.call(
            "wait",
            "--for=jsonpath={.status.finished}=true",
            "backups.k8up.io/" + backup_name,
            "--timeout=840s",
        )
        completed = resources.get("backups.k8up.io", backup_name)
        if not any(
            c["type"] == "Completed"
            and c["status"] == "True"
            and c["reason"] == "Succeeded"
            for c in completed.get("status", {}).get("conditions", [])
        ):
            raise RuntimeError("Real source capture failed; no recovery point accepted")
        path = f"/{source['namespace']}-{app}.tar"
        snapshots = [
            s["spec"]
            for s in resources.get("snapshots.k8up.io")["items"]
            if s["spec"].get("repository")
            == backend(source, resources.name)["local"]["mountPath"]
            and s["spec"].get("paths") == [path]
        ]
        if not snapshots:
            raise RuntimeError(
                "Successful Job has no snapshot for the expected source/path"
            )
        selected = max(snapshots, key=lambda value: value["date"])
        captured_at = datetime.datetime.fromisoformat(
            selected["date"].replace("Z", "+00:00")
        )
        started_at = datetime.datetime.fromisoformat(
            backup["metadata"]["creationTimestamp"].replace("Z", "+00:00")
        )
        if captured_at < started_at:
            raise RuntimeError(
                "Successful operation has no fresh source snapshot; old artifacts are not accepted"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", selected["id"]):
            raise RuntimeError("Capture did not expose a full immutable snapshot ID")
        record = {
            "app": app,
            "cluster": source["cluster"],
            "namespace": source["namespace"],
            "profile": source["profile"],
            "snapshot": selected["id"],
            "date": selected["date"],
            "path": path,
            "backup_uid": backup["metadata"]["uid"],
            "restored": False,
        }
        directory = ROOT / ".private/backup-captures"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = directory / f"{app}-{selected['id']}.json"
        output.write_text(json.dumps(record, sort_keys=True) + "\n")
        output.chmod(0o600)
        success = True
        print(json.dumps(record))
        return record
    finally:
        if not success:
            resources.call(
                "delete",
                "backups.k8up.io",
                backup_name,
                "--ignore-not-found",
                "--cascade=foreground",
                "--wait=true",
                check=False,
            )
        resources.cleanup()


def unpack(archive, app, source):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle:
            path = Path(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (member.isdir() or member.isfile())
            ):
                raise RuntimeError("Unsafe recovery archive member")
            if member.isfile():
                if member.name in files:
                    raise RuntimeError("Duplicate recovery archive member")
                files[member.name] = bundle.extractfile(member).read()
    metadata = json.loads(files["source.json"])
    if (
        metadata.get("app") != app
        or metadata.get("cluster") != source["cluster"]
        or metadata.get("namespace") != source["namespace"]
    ):
        raise RuntimeError(
            "Archive identity does not match requested app/cluster/namespace"
        )
    checked = set()
    for line in files["SHA256SUMS"].decode().splitlines():
        digest, name = line.split("  ", 1)
        name = name.removeprefix("./")
        if name not in files or hashlib.sha256(files[name]).hexdigest() != digest:
            raise RuntimeError("Recovery artifact checksum mismatch")
        checked.add(name)
    if checked != set(files) - {"SHA256SUMS"}:
        raise RuntimeError("Recovery manifest does not cover every file")
    return files, metadata


def recovery_reader(resources, source, password, inspect_restored_files=False):
    deadline = 10800 if inspect_restored_files else 1800
    resources.create(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "recovery-key"},
            "stringData": {"password": password},
        }
    )
    node = TARGETS[resources.cluster][1][-1]
    resources.create(
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "repository"},
            "spec": {
                "restartPolicy": "Never",
                "activeDeadlineSeconds": deadline,
                "automountServiceAccountToken": False,
                "securityContext": SECURITY,
                "nodeSelector": {"kubernetes.io/hostname": node},
                "containers": [
                    {
                        "name": "restic",
                        "image": RESTIC_IMAGE,
                        "command": ["sh", "-ec", f"exec sleep {deadline}"],
                        "securityContext": CONTAINER_SECURITY,
                        "resources": {
                            "requests": {"cpu": "50m", "memory": "64Mi"},
                            "limits": {"cpu": "1", "memory": "1Gi"},
                        },
                        "env": [
                            {
                                "name": "RESTIC_REPOSITORY",
                                "value": backend(source, "unused")["local"][
                                    "mountPath"
                                ],
                            },
                            {
                                "name": "RESTIC_PASSWORD",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": "recovery-key",
                                        "key": "password",
                                    }
                                },
                            },
                            {"name": "RESTIC_CACHE_DIR", "value": "/work/cache"},
                        ],
                        "volumeMounts": [
                            {"name": "repository", "mountPath": "/repository"},
                            {"name": "work", "mountPath": "/work"},
                            {"name": "tmp", "mountPath": "/tmp"},
                        ],
                    },
                    {
                        "name": "transfer",
                        "image": PYTHON_IMAGE,
                        "command": [
                            "python3",
                            "-m",
                            "http.server",
                            "8080",
                            "--bind",
                            "127.0.0.1",
                            "--directory",
                            "/work",
                        ],
                        "readinessProbe": {
                            "exec": {
                                "command": [
                                    "python3",
                                    "-c",
                                    "import socket; socket.create_connection(('127.0.0.1',8080),1).close()",
                                ]
                            },
                            "periodSeconds": 2,
                        },
                        "securityContext": CONTAINER_SECURITY,
                        "resources": {
                            "requests": {"cpu": "10m", "memory": "32Mi"},
                            "limits": {"cpu": "250m", "memory": "64Mi"},
                        },
                        "volumeMounts": [
                            {"name": "work", "mountPath": "/work", "readOnly": True}
                        ]
                        + (
                            [{"name": "repository", "mountPath": "/repository", "readOnly": True}]
                            if inspect_restored_files
                            else []
                        ),
                    },
                ],
                "volumes": [
                    {
                        "name": "repository",
                        "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"},
                    },
                    {"name": "work", "emptyDir": {}},
                    {"name": "tmp", "emptyDir": {}},
                ],
            },
        }
    )
    resources.call("wait", "--for=condition=Ready", "pod/repository", "--timeout=180s")


def postgres_restore(resources, source, files, metadata):
    db = json.loads(files["database.json"])
    if db.get("tablespaces"):
        raise RuntimeError(
            "Non-default tablespaces need explicit reviewed recovery storage mapping"
        )
    image = metadata["image_id"].removeprefix("docker-pullable://")
    if "@sha256:" not in image:
        raise RuntimeError("Recovery image is not immutable")
    # PostgreSQL 17 GRANTED BY uses the bootstrap role's implicit ADMIN rights.
    # Preserve that identity rather than weakening membership/grantor semantics.
    admin = db["bootstrap_role"]
    password = secrets.token_urlsafe(32)
    for role in source["login_roles"]:
        root = "secrets/" + role["secret"] + "/"
        user = role.get("user") or files[root + role["user_key"]].decode()
        if user == admin:
            password = files[root + role["password_key"]].decode()
    resources.create(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "database-password"},
            "stringData": {"password": password},
        }
    )
    resources.create(
        {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "database",
                "annotations": {"k8up.io/backup": "false"},
            },
            "spec": {
                "storageClassName": "local-path",
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "2Gi"}},
            },
        }
    )
    node = TARGETS[resources.cluster][1][-1]
    resources.create(
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "database"},
            "spec": {
                "restartPolicy": "Never",
                "automountServiceAccountToken": False,
                "securityContext": SECURITY,
                "nodeSelector": {"kubernetes.io/hostname": node},
                "initContainers": [
                    {
                        "name": "runtime",
                        "image": image,
                        "command": ["sh", "-ec", "mkdir -p /runtime/socket"],
                        "securityContext": CONTAINER_SECURITY,
                        "volumeMounts": [{"name": "runtime", "mountPath": "/runtime"}],
                    }
                ],
                "containers": [
                    {
                        "name": "postgres",
                        "image": image,
                        "args": [
                            "postgres",
                            "-c",
                            "shared_buffers=64MB",
                            "-c",
                            "max_connections=20",
                            "-c",
                            "shared_preload_libraries="
                            + db.get("shared_preload_libraries", ""),
                        ],
                        "env": [
                            {"name": "POSTGRES_USER", "value": admin},
                            {"name": "POSTGRES_DB", "value": "postgres"},
                            {
                                "name": "PGDATA",
                                "value": "/var/lib/postgresql/data/pgdata",
                            },
                            *[
                                {
                                    "name": key,
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "database-password",
                                            "key": "password",
                                        }
                                    },
                                }
                                for key in ["POSTGRES_PASSWORD", "PGPASSWORD"]
                            ],
                        ],
                        "securityContext": {
                            **CONTAINER_SECURITY,
                            "readOnlyRootFilesystem": False,
                        },
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "256Mi"},
                            "limits": {"cpu": "2", "memory": "2Gi"},
                        },
                        "volumeMounts": [
                            {"name": "data", "mountPath": "/var/lib/postgresql/data"},
                            {"name": "tmp", "mountPath": "/tmp"},
                            {
                                "name": "runtime",
                                "mountPath": "/var/run/postgresql",
                                "subPath": "socket",
                            },
                        ],
                        "readinessProbe": {
                            "exec": {
                                "command": [
                                    "pg_isready",
                                    "-h",
                                    "127.0.0.1",
                                    "-U",
                                    admin,
                                ]
                            },
                            "periodSeconds": 2,
                        },
                    }
                ],
                "volumes": [
                    {
                        "name": "data",
                        "persistentVolumeClaim": {"claimName": "database"},
                    },
                    {"name": "tmp", "emptyDir": {}},
                    {"name": "runtime", "emptyDir": {}},
                ],
            },
        }
    )
    resources.call("wait", "--for=condition=Ready", "pod/database", "--timeout=240s")

    def sql(value, database="postgres"):
        return resources.call(
            "exec",
            "-i",
            "database",
            "-c",
            "postgres",
            "--",
            "psql",
            "-X",
            "-h",
            "127.0.0.1",
            "-U",
            admin,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            value=value,
        ).stdout

    # Validate the complete retrieved archive before creating/importing app data.
    resources.call(
        "exec",
        "-i",
        "database",
        "-c",
        "postgres",
        "--",
        "pg_restore",
        "--exit-on-error",
        "--file=/dev/null",
        value=files["database.dump"],
        binary=True,
    )
    roles = files["roles.sql"].decode()
    bootstrap_create = f"CREATE ROLE {qident(admin)};\n"
    if roles.count(bootstrap_create) != 1:
        raise RuntimeError(
            "Role archive does not contain exactly one matching bootstrap role"
        )
    sql(roles.replace(bootstrap_create, "", 1))
    sql(
        f"CREATE DATABASE {qident(db['database'])} OWNER {qident(db['database_owner'])};"
    )
    resources.call(
        "exec",
        "-i",
        "database",
        "-c",
        "postgres",
        "--",
        "pg_restore",
        "-h",
        "127.0.0.1",
        "-U",
        admin,
        "--single-transaction",
        "--exit-on-error",
        "--dbname=" + db["database"],
        value=files["database.dump"],
        binary=True,
    )
    restored_extensions = json.loads(
        sql(
            "SELECT json_agg(json_build_object('name',extname,'version',extversion)) FROM pg_extension;",
            db["database"],
        )
    )
    if sorted(restored_extensions, key=lambda e: e["name"]) != sorted(
        db["extensions"], key=lambda e: e["name"]
    ):
        raise RuntimeError("Recovered PostgreSQL extensions/versions differ")
    for role in source["login_roles"]:
        root = "secrets/" + role["secret"] + "/"
        user = role.get("user") or files[root + role["user_key"]].decode()
        credential = files[root + role["password_key"]].decode()
        resources.call(
            "exec",
            "-i",
            "database",
            "-c",
            "postgres",
            "--",
            "psql",
            "-X",
            "-h",
            "127.0.0.1",
            "-U",
            admin,
            "-d",
            db["database"],
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "\\password " + qident(user),
            value=credential + "\n" + credential + "\n",
        )
        shell = 'IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -X -h 127.0.0.1 -U "$1" -d "$2" -v ON_ERROR_STOP=1 -Atc "SELECT current_database()"'
        result = resources.call(
            "exec",
            "-i",
            "database",
            "-c",
            "postgres",
            "--",
            "sh",
            "-ec",
            shell,
            "--",
            user,
            db["database"],
            value=credential + "\n",
        ).stdout.strip()
        if result != db["database"]:
            raise RuntimeError(
                "Recovered application database role cannot authenticate"
            )
    if metadata["app"] == "immich-db":
        query = "SELECT json_build_object('users',(SELECT count(*) FROM \"user\"),'assets',(SELECT count(*) FROM \"asset\"));"
    else:
        query = "SELECT json_build_object('tables',(SELECT count(*) FROM pg_tables WHERE schemaname='public'),'users',(SELECT count(*) FROM \"LiteLLM_UserTable\"),'virtual_keys',(SELECT count(*) FROM \"LiteLLM_VerificationToken\"),'config_entries',(SELECT count(*) FROM \"LiteLLM_Config\"));"
    functional = json.loads(sql(query, db["database"]))
    return {
        "extensions_match": True,
        "application_roles_authenticated": True,
        "functional_queries": functional,
        "image": image,
    }


def restore(app, snapshot, target_cluster=None, keep_target=False):
    source = SOURCES[app]
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        raise RuntimeError(
            "Restore requires a full immutable snapshot ID, never latest"
        )
    target = target_cluster or source["cluster"]
    namespace = f"backup-restore-{app}-{uuid.uuid4().hex[:8]}"
    resources = Resources(target, namespace, own_namespace=True)
    retained = False
    try:
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": namespace,
                    "labels": {"pod-security.kubernetes.io/enforce": "baseline"},
                },
            }
        )
        resources.create(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "no-outbound-integrations"},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [],
                },
            }
        )
        recovery_reader(resources, source, keychain(source))
        resources.call("exec", "repository", "--", "restic", "check", "--read-data")
        path = f"/{source['namespace']}-{app}.tar"
        remote = resources.call(
            "exec",
            "repository",
            "-c",
            "restic",
            "--",
            "sh",
            "-ec",
            'restic dump "$1" "$2" > /work/bundle.tar; sha256sum /work/bundle.tar',
            "--",
            snapshot,
            path,
        ).stdout.split()[0]
        with port_forward(resources, "repository", 8080) as address:
            with urllib.request.urlopen(
                address + "/bundle.tar", timeout=120
            ) as response:
                data = response.read(512 * 1024 * 1024 + 1)
                if (
                    len(data) != int(response.headers["Content-Length"])
                    or len(data) > 512 * 1024 * 1024
                ):
                    raise RuntimeError(
                        "Recovery transfer length mismatch or staging bound exceeded"
                    )
        if hashlib.sha256(data).hexdigest() != remote:
            raise RuntimeError(
                "Recovery transfer SHA-256 differs from repository-side artifact"
            )
        files, metadata = unpack(data, app, source)
        proof = postgres_restore(resources, source, files, metadata)
        record = {
            "app": app,
            "snapshot": snapshot,
            "target_cluster": target,
            "isolated_restore_passed": True,
            "restored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "recovery_namespace": namespace,
            "proof_id": resources.run_id,
            "target_preserved": keep_target,
            **proof,
        }
        if keep_target:
            for name in source["recovery_secrets"]:
                prefix = f"secrets/{name}/"
                values = {
                    path.removeprefix(prefix): base64.b64encode(value).decode()
                    for path, value in files.items()
                    if path.startswith(prefix)
                }
                if not values:
                    raise RuntimeError(
                        "A required recovery Secret is absent from the archive"
                    )
                resources.create(
                    {
                        "apiVersion": "v1",
                        "kind": "Secret",
                        "metadata": {"name": name},
                        "type": "Opaque",
                        "data": values,
                    }
                )
            resources.call(
                "delete", "pod", "repository", "--wait=true", "--timeout=120s"
            )
            resources.call("delete", "secret", "recovery-key")
            retained = True
            record["recovery_secrets"] = source["recovery_secrets"]
        directory = ROOT / ".private/backup-restores"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = directory / f"{app}-{snapshot}.json"
        output.write_text(json.dumps(record, sort_keys=True) + "\n")
        output.chmod(0o600)
        print(json.dumps(record))
        return record
    finally:
        if not retained:
            resources.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "restore", "prove"])
    parser.add_argument("app", choices=SOURCES)
    parser.add_argument("--cluster", required=True, choices=TARGETS)
    parser.add_argument("--snapshot")
    parser.add_argument("--target-cluster", choices=TARGETS)
    parser.add_argument(
        "--keep-target",
        action="store_true",
        help="Keep the verified isolated database and required app Secrets for reviewed recovery",
    )
    args = parser.parse_args()
    try:
        if args.keep_target and args.action != "restore":
            parser.error("--keep-target applies only to an explicit snapshot restore")
        if SOURCES[args.app]["cluster"] != args.cluster:
            parser.error(
                "APP does not belong to the explicitly selected source CLUSTER"
            )
        if args.action == "prove":
            captured = capture(args.app)
            restore(args.app, captured["snapshot"], args.target_cluster)
            return
        if args.action == "capture":
            capture(args.app)
        else:
            if not args.snapshot:
                parser.error("restore requires --snapshot")
            restore(args.app, args.snapshot, args.target_cluster, args.keep_target)
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
