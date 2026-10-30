#!/usr/bin/env python3
"""Prove synthetic PostgreSQL export/restore and fail-closed K8up streaming."""

import argparse
import json
import secrets
import shlex
import subprocess
import sys

from k8up_pilot import CONTAINER_SECURITY, SECURITY, TARGETS, Pilot, run

IMAGES = {
    "14": "ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23",
    "17": "docker.io/library/postgres:17.5@sha256:aadf2c0696f5ef357aa7a68da995137f0cf17bad0bf6e1f17de06ae5c769b302",
}
RESTIC_IMAGE = "restic/restic:0.19.1@sha256:136600b6ff6843d61d355f7f71f460a166429f35de6fd11b568fece3c9a4d510"
EXPORT = """set -eu
umask 077
a=$(mktemp /tmp/pg-export.XXXXXX)
pg_dump --format=custom --file="$a"
pg_restore --exit-on-error --file=/dev/null "$a"
cat "$a"
rm -f "$a"
"""
SIGNATURE = "SELECT count(*)::text || ':' || md5(string_agg(id::text || ':' || value || ':' || encode(payload,'hex'),',' ORDER BY id)) FROM archive.records;"


class PostgresPilot(Pilot):
    def __init__(self, cluster, major):
        super().__init__(cluster, kind="postgres")
        self.image = IMAGES[major]
        self.major = major
        self.password = secrets.token_urlsafe(48)
        self.backend = {
            "local": {"mountPath": f"/repository/{self.repository}"},
            "repoPasswordSecretRef": {"name": "pilot-repository", "key": "password"},
            "volumeMounts": [{"name": "repository", "mountPath": "/repository"}],
        }

    def sql(self, pod, sql, check=True):
        return subprocess.run(
            self.kubectl
            + [
                "-n",
                self.namespace,
                "exec",
                "-i",
                pod,
                "--",
                "psql",
                "-X",
                "-h",
                "127.0.0.1",
                "-U",
                "fixture",
                "-d",
                "fixture",
                "-v",
                "ON_ERROR_STOP=1",
                "-At",
            ],
            input=sql,
            text=True,
            capture_output=True,
            check=check,
        )

    def database(self, name, node):
        self.pvc(name, False, size="256Mi")
        env = [
            {"name": "POSTGRES_USER", "value": "fixture"},
            {"name": "POSTGRES_DB", "value": "fixture"},
            {"name": "PGDATA", "value": "/var/lib/postgresql/data/pgdata"},
        ]
        env += [
            {
                "name": key,
                "valueFrom": {
                    "secretKeyRef": {"name": "fixture-password", "key": "password"}
                },
            }
            for key in ("POSTGRES_PASSWORD", "PGPASSWORD")
        ]
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": name, "labels": {"pilot-db": name}},
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
                    "initContainers": [
                        {
                            "name": "runtime-directory",
                            "image": self.image,
                            "command": ["sh", "-ec", "mkdir -p /runtime/pgsocket"],
                            "securityContext": CONTAINER_SECURITY,
                            "volumeMounts": [
                                {"name": "runtime", "mountPath": "/runtime"}
                            ],
                            "resources": {
                                "requests": {"cpu": "10m", "memory": "16Mi"},
                                "limits": {"cpu": "100m", "memory": "32Mi"},
                            },
                        }
                    ],
                    "containers": [
                        {
                            "name": "postgres",
                            "image": self.image,
                            "args": [
                                "postgres",
                                "-c",
                                "shared_buffers=32MB",
                                "-c",
                                "max_connections=20",
                            ],
                            "env": env,
                            "securityContext": {
                                **CONTAINER_SECURITY,
                                "readOnlyRootFilesystem": False,
                            },
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "128Mi"},
                                "limits": {"cpu": "1", "memory": "512Mi"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "data",
                                    "mountPath": "/var/lib/postgresql/data",
                                },
                                {"name": "tmp", "mountPath": "/tmp"},
                                {
                                    "name": "runtime",
                                    "mountPath": "/var/run/postgresql",
                                    "subPath": "pgsocket",
                                },
                            ],
                            "readinessProbe": {
                                "exec": {
                                    "command": [
                                        "pg_isready",
                                        "-h",
                                        "127.0.0.1",
                                        "-U",
                                        "fixture",
                                        "-d",
                                        "fixture",
                                    ]
                                },
                                "periodSeconds": 2,
                            },
                        }
                    ],
                    "volumes": [
                        {"name": "data", "persistentVolumeClaim": {"claimName": name}},
                        {"name": "tmp", "emptyDir": {}},
                        {"name": "runtime", "emptyDir": {}},
                    ],
                },
            }
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
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name},
                "spec": {
                    "selector": {"pilot-db": name},
                    "ports": [{"port": 5432, "targetPort": 5432}],
                },
            }
        )

    def exporter(self, name, app, command):
        labels = {
            "backup.krapulax.dev/app": app,
            "backup.krapulax.dev/policy": "critical-6h",
            "backup.krapulax.dev/strategy": "postgres-dump",
        }
        self.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "PreBackupPod",
                "metadata": {"name": name, "labels": labels},
                "spec": {
                    "backupCommand": "sh -ec " + shlex.quote(command),
                    "fileExtension": ".dump",
                    "pod": {
                        "spec": {
                            "automountServiceAccountToken": False,
                            "securityContext": SECURITY,
                            "containers": [
                                {
                                    "name": "export",
                                    "image": self.image,
                                    "command": ["sleep", "600"],
                                    "securityContext": CONTAINER_SECURITY,
                                    "env": [
                                        {"name": "PGHOST", "value": "source-a"},
                                        {"name": "PGUSER", "value": "fixture"},
                                        {"name": "PGDATABASE", "value": "fixture"},
                                        {
                                            "name": "PGPASSWORD",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "fixture-password",
                                                    "key": "password",
                                                }
                                            },
                                        },
                                    ],
                                    "volumeMounts": [
                                        {"name": "tmp", "mountPath": "/tmp"}
                                    ],
                                    "resources": {
                                        "requests": {"cpu": "50m", "memory": "128Mi"},
                                        "limits": {"cpu": "500m", "memory": "512Mi"},
                                    },
                                }
                            ],
                            "volumes": [
                                {"name": "tmp", "emptyDir": {"sizeLimit": "1Gi"}}
                            ],
                        },
                    },
                },
            }
        )

    def backup(self, name, expect_success=True):
        self.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "Backup",
                "metadata": {"name": name},
                "spec": {
                    "backend": self.backend,
                    "podConfigRef": {"name": "runner"},
                    "clusterName": self.namespace,
                    "activeDeadlineSeconds": 240 if expect_success else 45,
                    "successfulJobsHistoryLimit": 4,
                    "failedJobsHistoryLimit": 4,
                    "labelSelectors": [
                        {
                            "matchLabels": {
                                "backup.krapulax.dev/app": "fixture",
                                "backup.krapulax.dev/policy": "critical-6h",
                            }
                        }
                    ],
                },
            }
        )
        self.command(
            "wait",
            "--for=jsonpath={.status.finished}=true",
            f"backups.k8up.io/{name}",
            "--timeout=420s",
            capture_output=True,
        )
        conditions = (
            self.get("backups.k8up.io", name).get("status", {}).get("conditions", [])
        )
        completed = next(
            (
                c
                for c in conditions
                if c["type"] == "Completed" and c["status"] == "True"
            ),
            None,
        )
        if not completed or completed["reason"] != (
            "Succeeded" if expect_success else "Failed"
        ):
            raise RuntimeError(f"Unexpected {name} capture result: {conditions}")
        print(
            f"PASS: {name} {'succeeded with selected exporter only' if expect_success else 'failed closed as required'}",
            flush=True,
        )

    def reader(self):
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "recovery-key"},
                "stringData": {"password": self.password},
            }
        )
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "recovery"},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": SECURITY,
                    "nodeSelector": {"kubernetes.io/hostname": self.nodes[1]},
                    "tolerations": [
                        {
                            "key": "node-role.kubernetes.io/control-plane",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        }
                    ],
                    "containers": [
                        {
                            "name": "restic",
                            "image": RESTIC_IMAGE,
                            "command": ["sh", "-ec", "restic version; exec sleep 1800"],
                            "securityContext": CONTAINER_SECURITY,
                            "env": [
                                {
                                    "name": "RESTIC_REPOSITORY",
                                    "value": f"/repository/{self.repository}",
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
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "64Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"},
                            },
                            "volumeMounts": [
                                {"name": "repository", "mountPath": "/repository"},
                                {"name": "tmp", "mountPath": "/tmp"},
                                {"name": "work", "mountPath": "/work"},
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "repository",
                            "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"},
                        },
                        {"name": "tmp", "emptyDir": {}},
                        {"name": "work", "emptyDir": {}},
                    ],
                },
            }
        )
        self.command(
            "wait",
            "--for=condition=Ready",
            "pod/recovery",
            "--timeout=120s",
            capture_output=True,
        )

    def dump(self, snapshot, path, check=True):
        return subprocess.run(
            self.kubectl
            + [
                "-n",
                self.namespace,
                "exec",
                "recovery",
                "--",
                "restic",
                "dump",
                snapshot,
                path,
            ],
            capture_output=True,
            check=check,
        )

    def validate_archive(self, archive, check=True):
        return subprocess.run(
            self.kubectl
            + [
                "-n",
                self.namespace,
                "exec",
                "-i",
                "source-b",
                "--",
                "pg_restore",
                "--exit-on-error",
                "--file=/dev/null",
            ],
            input=archive,
            capture_output=True,
            check=check,
        )

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
                "stringData": {"password": self.password},
            }
        )
        self.create(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "fixture-password"},
                "stringData": {"password": secrets.token_urlsafe(32)},
            }
        )
        self.create(
            {
                "apiVersion": "k8up.io/v1",
                "kind": "PodConfig",
                "metadata": {"name": "runner"},
                "spec": {
                    "template": {
                        "spec": {
                            "securityContext": SECURITY,
                            "containers": [
                                {
                                    "name": "k8up",
                                    "securityContext": CONTAINER_SECURITY,
                                    "env": [
                                        {
                                            "name": "RESTIC_CACHE_DIR",
                                            "value": "/k8up/cache",
                                        }
                                    ],
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
        self.database("source-a", self.nodes[0])
        self.database("source-b", self.nodes[1])
        payload = secrets.token_hex(2048)
        self.sql(
            "source-a",
            f"""CREATE ROLE fixture_owner NOLOGIN;
CREATE SCHEMA archive AUTHORIZATION fixture_owner;
SET ROLE fixture_owner;
CREATE TABLE archive.records (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, value text NOT NULL UNIQUE, payload bytea NOT NULL);
INSERT INTO archive.records(value,payload) SELECT 'record-' || g,decode(md5(g::text),'hex') FROM generate_series(1,250) g;
INSERT INTO archive.records(value,payload) VALUES ('árvíztűrő tükörfúrógép — 照片',decode('{payload}','hex'));
CREATE VIEW archive.record_names AS SELECT id,value FROM archive.records;
CREATE FUNCTION archive.total() RETURNS bigint LANGUAGE sql STABLE AS $$ SELECT count(*) FROM archive.records $$;
""",
        )
        signature = self.sql("source-a", SIGNATURE).stdout.strip()
        self.exporter("fixture", "fixture", EXPORT)
        self.exporter(
            "unselected", "unselected", "echo ERROR-unselected-exporter >&2; exit 91"
        )
        accepted = []
        for name in ("first", "second"):
            self.backup(name)
            snapshots = self.get("snapshots.k8up.io")["items"]
            new = [
                s["spec"]
                for s in snapshots
                if s["spec"]["id"] not in {s["id"] for s in accepted}
            ]
            if (
                len(new) != 1
                or len(new[0].get("paths", [])) != 1
                or not new[0]["paths"][0].endswith(".dump")
            ):
                raise RuntimeError(
                    f"Capture did not contain exactly one selected database stream: {new}"
                )
            accepted.append(new[0])
        self.command(
            "patch",
            "prebackuppods.k8up.io",
            "fixture",
            "--type=merge",
            "-p",
            json.dumps(
                {
                    "spec": {
                        "backupCommand": "sh -ec "
                        + shlex.quote("printf partial-archive; exit 42")
                    }
                }
            ),
            capture_output=True,
        )
        self.backup("partial-producer", expect_success=False)
        truncated = EXPORT.replace(
            "pg_restore --exit-on-error",
            'truncate -s 128 "$a"\npg_restore --exit-on-error',
        )
        self.command(
            "patch",
            "prebackuppods.k8up.io",
            "fixture",
            "--type=merge",
            "-p",
            json.dumps({"spec": {"backupCommand": "sh -ec " + shlex.quote(truncated)}}),
            capture_output=True,
        )
        self.backup("invalid-archive", expect_success=False)
        self.command(
            "delete", "snapshots.k8up.io", "--all", "--wait=true", capture_output=True
        )
        self.command(
            "delete", "secret", "pilot-repository", "--wait=true", capture_output=True
        )
        self.reader()
        catalog = json.loads(
            self.command(
                "exec",
                "recovery",
                "--",
                "restic",
                "snapshots",
                "--json",
                capture_output=True,
            ).stdout
        )
        chosen = []
        for captured in accepted:
            matches = [s for s in catalog if s["id"].startswith(captured["id"])]
            if len(matches) != 1 or len(matches[0]["id"]) != 64:
                raise RuntimeError(
                    "Cannot independently resolve the accepted full snapshot ID"
                )
            chosen.append(matches[0])
        if (
            chosen[0]["paths"] != chosen[1]["paths"]
            or chosen[0]["hostname"] != chosen[1]["hostname"]
        ):
            raise RuntimeError(
                f"Unstable stream identity: {[(s['hostname'],s['paths']) for s in chosen]}"
            )
        selected = chosen[0]
        source_path = selected["paths"][0]
        if self.dump("0" * 64, source_path, check=False).returncode == 0:
            raise RuntimeError("Missing snapshot ID was accepted")
        if (
            self.dump(selected["id"], "/not-this-database.dump", check=False).returncode
            == 0
        ):
            raise RuntimeError("Wrong source path was accepted")
        wrong_key = subprocess.run(
            self.kubectl
            + [
                "-n",
                self.namespace,
                "exec",
                "recovery",
                "--",
                "env",
                "RESTIC_PASSWORD=deliberately-wrong",
                "restic",
                "snapshots",
            ],
            capture_output=True,
        )
        if wrong_key.returncode == 0:
            raise RuntimeError("Wrong recovery password was accepted")
        archive = self.dump(selected["id"], source_path).stdout
        self.validate_archive(archive)
        if self.validate_archive(archive[:128], check=False).returncode == 0:
            raise RuntimeError("Truncated recovery archive was accepted")
        self.sql("source-b", "CREATE ROLE fixture_owner NOLOGIN;")
        subprocess.run(
            self.kubectl
            + [
                "-n",
                self.namespace,
                "exec",
                "-i",
                "source-b",
                "--",
                "pg_restore",
                "-h",
                "127.0.0.1",
                "-U",
                "fixture",
                "--exit-on-error",
                "--dbname=fixture",
            ],
            input=archive,
            capture_output=True,
            check=True,
        )
        if self.sql("source-b", SIGNATURE).stdout.strip() != signature:
            raise RuntimeError("Imported rows, non-ASCII or binary values differ")
        if self.sql(
            "source-b",
            "SELECT tableowner FROM pg_tables WHERE schemaname='archive' AND tablename='records'; SELECT archive.total();",
        ).stdout.splitlines() != ["fixture_owner", "251"]:
            raise RuntimeError("Ownership or stored function was not recovered")
        if (
            self.sql(
                "source-b",
                "INSERT INTO archive.records(value,payload) VALUES ('continued',decode('0102','hex')) RETURNING id;",
            ).stdout.splitlines()[0]
            != "252"
        ):
            raise RuntimeError("Identity sequence did not continue")
        if (
            self.sql(
                "source-b",
                "INSERT INTO archive.records(value,payload) VALUES ('record-1',decode('01','hex'));",
                check=False,
            ).returncode
            == 0
        ):
            raise RuntimeError("Restored uniqueness constraint was not enforced")
        print(
            f"PASS PG{self.major}: isolated role/schema/row/binary/sequence recovery on {self.nodes[1]}, selected exporter only, stable snapshot identity, producer/truncation/wrong-ID/path/key rejection, recovery without original Snapshot CRs/Secret",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=TARGETS)
    parser.add_argument("--major", required=True, choices=IMAGES)
    args = parser.parse_args()
    return run(PostgresPilot(args.cluster, args.major))


if __name__ == "__main__":
    sys.exit(main())
