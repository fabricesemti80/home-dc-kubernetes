#!/usr/bin/env python3
"""One-time K8up retirement; originals and the new Backrest prefixes are excluded."""

import argparse
import json
from pathlib import Path
import subprocess
import uuid

from backrest import ROOT, client, require_recovery

ARCHIVE = "94abc54"
CRDS = [
    name + ".k8up.io"
    for name in [
        "archives",
        "backups",
        "checks",
        "podconfigs",
        "prebackuppods",
        "prunes",
        "restores",
        "schedules",
        "snapshots",
    ]
]


def run(args, value=None, check=True):
    result = subprocess.run(
        args, input=value, text=True, capture_output=True, timeout=300
    )
    if check and result.returncode:
        raise RuntimeError("Retirement command failed; private diagnostics suppressed")
    return result


def retire(cluster):
    suffix, namespace = (
        ("app", "media") if cluster == "app-cluster" else ("infra", "ai")
    )
    with client(cluster) as (call, resources):
        require_recovery(call, cluster)
        kubectl = resources.kubectl
    # Preserve code provenance and derive exact old policy objects from the archive.
    run(["git", "fetch", "origin", "backup/k8up-before-backrest-20261030"])
    policy = run(
        [
            "git",
            "show",
            f"{ARCHIVE}:kubernetes/apps/{cluster}/storage/k8up/config/{namespace}/policy.yaml",
        ]
    ).stdout
    hub = ["kubectl", "--kubeconfig", str(ROOT / "kubeconfig"), "-n", "argo-system"]
    legacy = run(
        hub + ["get", "application", "k8up-" + suffix, "-o", "json"], check=False
    )
    if legacy.returncode == 0:
        app = json.loads(legacy.stdout)
        if app["spec"]["destination"]["name"] != cluster or any(
            s.get("path", "").startswith("kubernetes/apps/")
            and "/storage/k8up" not in s["path"]
            for s in app["spec"]["sources"]
        ):
            raise RuntimeError("Legacy Argo ownership differs; refusing retirement")
        allowed = {
            "post-delete-finalizer.argocd.argoproj.io",
            "post-delete-finalizer.argocd.argoproj.io/cleanup",
        }
        if set(app["metadata"].get("finalizers", [])) - allowed:
            raise RuntimeError(
                "Unexpected/cascading Argo finalizers; none were stripped"
            )
        # The legacy path is gone from main; its native post-delete hooks still
        # need a resolvable source while retiring the registration.
        for source in app["spec"]["sources"]:
            if (
                source.get("repoURL")
                == "https://github.com/fabricesemti80/home-dc-kubernetes.git"
            ):
                source["targetRevision"] = ARCHIVE
        run(
            hub
            + [
                "patch",
                "application",
                "k8up-" + suffix,
                "--type=merge",
                "-p",
                json.dumps(
                    {
                        "spec": {
                            "syncPolicy": {"automated": None},
                            "sources": app["spec"]["sources"],
                        }
                    }
                ),
            ]
        )
    present = (
        run(
            kubectl + ["get", "crd", "schedules.k8up.io", "-o", "name"], check=False
        ).returncode
        == 0
    )
    if present:
        schedules = json.loads(
            run(kubectl + ["get", "schedules.k8up.io", "-A", "-o", "json"]).stdout
        )["items"]
        if any(
            s["metadata"]["namespace"] != namespace
            or s["metadata"]["name"] != "critical-6h"
            for s in schedules
        ):
            raise RuntimeError(
                "Unexpected K8up schedules exist; review them before retirement"
            )
        run(
            kubectl
            + [
                "-n",
                namespace,
                "delete",
                "schedules.k8up.io",
                "critical-6h",
                "--ignore-not-found",
            ]
        )
    cronjobs = json.loads(
        run(kubectl + ["-n", namespace, "get", "cronjobs", "-o", "json"]).stdout
    )["items"]
    for cronjob in cronjobs:
        if cronjob["metadata"]["name"].startswith("critical-6h-"):
            run(
                kubectl
                + ["-n", namespace, "delete", "cronjob", cronjob["metadata"]["name"]]
            )
    jobs = json.loads(run(kubectl + ["get", "jobs", "-A", "-o", "json"]).stdout)[
        "items"
    ]
    old_jobs = [
        job
        for job in jobs
        if any(
            owner.get("apiVersion", "").startswith("k8up.io/")
            for owner in job["metadata"].get("ownerReferences", [])
        )
        or (
            job["metadata"]["namespace"] == namespace
            and job["metadata"]["name"].startswith("critical-6h-")
        )
    ]
    if any(job.get("status", {}).get("active", 0) for job in old_jobs):
        raise RuntimeError(
            "Legacy scheduling stopped; active old jobs must finish before retrying retirement"
        )
    for job in old_jobs:
        run(
            kubectl
            + [
                "-n",
                job["metadata"]["namespace"],
                "delete",
                "job",
                job["metadata"]["name"],
                "--wait=true",
            ]
        )
    if legacy.returncode == 0:
        # Let Argo's known post-delete cleanup hook run; never strip its finalizers.
        run(
            hub
            + [
                "delete",
                "application",
                "k8up-" + suffix,
                "--cascade=orphan",
                "--wait=true",
            ]
        )
    if present:
        run(
            kubectl + ["-n", namespace, "delete", "-f", "-", "--ignore-not-found"],
            policy,
        )
        run(kubectl + ["delete", "crd", *CRDS, "--ignore-not-found"])
    run(
        kubectl
        + [
            "-n",
            namespace,
            "delete",
            "configmap",
            "backup-runtime",
            "--ignore-not-found",
        ]
    )
    run(
        kubectl
        + [
            "-n",
            "doppler-operator-system",
            "delete",
            "dopplersecret",
            "k8up-" + namespace + "-critical",
            "--ignore-not-found",
        ]
    )
    run(
        kubectl
        + [
            "-n",
            namespace,
            "delete",
            "secret",
            "k8up-source-credentials",
            "--ignore-not-found",
        ]
    )
    executor = run(
        kubectl
        + [
            "-n",
            namespace,
            "get",
            "rolebinding",
            "pod-executor-namespaced",
            "-o",
            "json",
        ],
        check=False,
    )
    if executor.returncode == 0:
        binding = json.loads(executor.stdout)
        if binding.get("roleRef", {}).get("name") != "k8up-executor" or binding.get(
            "subjects"
        ) != [
            {"kind": "ServiceAccount", "name": "pod-executor", "namespace": namespace}
        ]:
            raise RuntimeError(
                "Unexpected executor binding ownership; refusing removal"
            )
        run(
            kubectl
            + ["-n", namespace, "delete", "rolebinding", "pod-executor-namespaced"]
        )
        run(
            kubectl
            + [
                "-n",
                namespace,
                "delete",
                "serviceaccount",
                "pod-executor",
                "--ignore-not-found",
            ]
        )
    run(
        kubectl
        + [
            "-n",
            "backups",
            "delete",
            "deployment,service,serviceaccount,role,rolebinding,configmap",
            "-l",
            "app.kubernetes.io/instance=k8up",
            "--ignore-not-found",
        ]
    )
    run(
        kubectl
        + [
            "delete",
            "clusterrole,clusterrolebinding",
            "-l",
            "app.kubernetes.io/instance=k8up",
            "--ignore-not-found",
        ]
    )
    # Direct NFS access is confined in code to known obsolete repository paths.
    paths = (
        ["app-cluster/media/critical-6h", "app-cluster/media/photos-daily"]
        if suffix == "app"
        else ["infra-cluster/ai/critical-6h", "infra-cluster/network/critical-6h"]
    )
    script = (
        "import pathlib,shutil,stat; roots="
        + repr(paths)
        + "\nfor relative in roots:\n p=pathlib.Path('/nas')/relative\n try:s=p.lstat()\n except FileNotFoundError:continue\n if not stat.S_ISDIR(s.st_mode) or s.st_uid!=1004 or p.is_symlink():raise RuntimeError('Unexpected legacy repository owner/type')\n if p.resolve()!=p:raise RuntimeError('Symlink in legacy repository ancestry')\n shutil.rmtree(p)\nprint('Enumerated legacy repositories removed; originals and Backrest prefixes untouched')\n"
    )
    name = "retire-k8up-" + uuid.uuid4().hex[:10]
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "namespace": "backups"},
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 1004,
                "runAsGroup": 65534,
                "supplementalGroups": [],
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "erase-legacy",
                    "image": "python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b",
                    "command": ["python3", "-c", script],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [{"name": "nas", "mountPath": "/nas"}],
                }
            ],
            "volumes": [
                {"name": "nas", "nfs": {"server": "10.0.40.2", "path": "/k8s-backup"}}
            ],
        },
    }
    run(kubectl + ["create", "-f", "-"], json.dumps(pod))
    run(
        kubectl
        + [
            "-n",
            "backups",
            "wait",
            "--for=jsonpath={.status.phase}=Succeeded",
            "pod/" + name,
            "--timeout=240s",
        ]
    )
    run(kubectl + ["-n", "backups", "delete", "pod", name, "--wait=true"])
    selector = (
        "app.kubernetes.io/instance=immich,app.kubernetes.io/controller=database"
        if suffix == "app"
        else "app.kubernetes.io/instance=litellm-postgres,app.kubernetes.io/name=postgres"
    )
    pods = json.loads(
        run(
            kubectl + ["-n", namespace, "get", "pods", "-l", selector, "-o", "json"]
        ).stdout
    )["items"]
    ready = [
        pod
        for pod in pods
        if not pod["metadata"].get("deletionTimestamp")
        and any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in pod["status"].get("conditions", [])
        )
    ]
    if len(ready) != 1:
        raise RuntimeError(
            "Cannot identify the exact database for obsolete-role cleanup"
        )
    marker = f"home-dc-kubernetes/{cluster}/{namespace}/postgres-backup"
    sql = f"""DO $cleanup$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='k8up_backup') THEN
  IF (SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname='k8up_backup') IS DISTINCT FROM '{marker}' THEN
   RAISE EXCEPTION 'Old backup role is not owned by this repository';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid=(SELECT oid FROM pg_roles WHERE rolname='k8up_backup') AND deptype='o') THEN
   RAISE EXCEPTION 'Old backup role owns objects; no objects were dropped';
  END IF;
  DROP OWNED BY k8up_backup;
  DROP ROLE k8up_backup;
 END IF;
END $cleanup$;
"""
    shell = 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
    run(
        kubectl
        + [
            "-n",
            namespace,
            "exec",
            "-i",
            ready[0]["metadata"]["name"],
            "--",
            "sh",
            "-ec",
            shell,
        ],
        sql,
    )
    print(
        json.dumps(
            {
                "cluster": cluster,
                "legacy_repositories_removed": paths,
                "new_backrest_repository_preserved": True,
                "source_volumes_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=["app-cluster", "infra-cluster"])
    parser.add_argument(
        "--database-imports-verified",
        action="store_true",
        required=True,
        help="Operator attests restored SQL was imported and application roles authenticated",
    )
    args = parser.parse_args()
    try:
        retire(args.cluster)
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(1, "ERROR: " + str(error) + "\n")
