#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["bcrypt==5.0.0"]
# ///
"""Bootstrap Backrest credentials without rotating existing repository keys."""

import argparse
import base64
import json
from pathlib import Path
import secrets
import stat
import subprocess
import uuid

import bcrypt

ROOT = Path(__file__).resolve().parents[1]


def run(args, value=None, check=True):
    result = subprocess.run(
        args, input=value, text=True, capture_output=True, timeout=180
    )
    if check and result.returncode:
        raise RuntimeError(
            f"{args[0]} operation failed; credential-bearing diagnostics suppressed"
        )
    return result


def bootstrap(cluster):
    config = "apps" if cluster == "app-cluster" else "infra"
    common = ["--project", "home-dc-kubernetes", "--config", config]
    names = json.loads(
        run(["doppler", "secrets", *common, "--only-names", "--json"]).stdout
    )

    def get(key):
        return (
            json.loads(
                run(["doppler", "secrets", "get", key, *common, "--json"]).stdout
            )[key]["computed"]
            if key in names
            else None
        )

    def save(key, value):
        run(
            [
                "doppler",
                "secrets",
                "set",
                key,
                *common,
                "--visibility",
                "masked",
                "--json",
                "--silent",
            ],
            value,
        )
        names.append(key) if isinstance(names, list) else names.update({key: True})
        if get(key) != value:
            raise RuntimeError("Doppler credential round-trip verification failed")

    service = "home-dc.backrest." + cluster
    escrow = run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            "restic",
            "-s",
            service,
            "-w",
        ],
        check=False,
    )
    if escrow.returncode not in [0, 44]:
        raise RuntimeError("Unlock/authorize the independent macOS Keychain first")
    recovery = escrow.stdout.removesuffix("\n") if escrow.returncode == 0 else None
    primary = get("BACKREST_REPOSITORY_PASSWORD")
    if primary is not None and not primary or recovery is not None and not recovery:
        raise RuntimeError("An existing repository key is empty; refusing replacement")
    if primary is not None and recovery is not None and primary != recovery:
        raise RuntimeError("Repository key copies differ; neither copy changed")
    if primary is None and recovery is None:
        kubeconfig = ROOT / (
            "kubeconfig" if config == "apps" else ".private/infra-cluster/kubeconfig"
        )
        kubectl = ["kubectl", "--kubeconfig", str(kubeconfig), "-n", "backups"]
        name = "backrest-key-probe-" + uuid.uuid4().hex[:10]
        script = (
            "import pathlib,stat; p=pathlib.Path('/nas/"
            + cluster
            + "/backrest/repository');\ntry:s=p.lstat()\nexcept FileNotFoundError:pass\nelse:\n if not stat.S_ISDIR(s.st_mode) or any(p.iterdir()):raise RuntimeError('Existing repository is not empty; recover its key instead')\n"
        )
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": name},
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
                        "name": "probe",
                        "image": "python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b",
                        "command": ["python3", "-c", script],
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "volumeMounts": [
                            {"name": "nas", "mountPath": "/nas", "readOnly": True}
                        ],
                    }
                ],
                "volumes": [
                    {
                        "name": "nas",
                        "nfs": {
                            "server": "10.0.40.2",
                            "path": "/k8s-backup",
                            "readOnly": True,
                        },
                    }
                ],
            },
        }
        created = False
        try:
            run(kubectl + ["create", "-f", "-"], json.dumps(pod))
            created = True
            run(
                kubectl
                + [
                    "wait",
                    "--for=jsonpath={.status.phase}=Succeeded",
                    "pod/" + name,
                    "--timeout=120s",
                ]
            )
        finally:
            if created:
                run(kubectl + ["delete", "pod", name, "--wait=true"])
    password = primary or recovery or secrets.token_urlsafe(48)
    if recovery is None:
        run(
            ["/usr/bin/security", "-i"],
            f"add-generic-password -a restic -s {service} -T /usr/bin/security -X {password.encode().hex()}\n",
        )
    if primary is None:
        save("BACKREST_REPOSITORY_PASSWORD", password)
    if (
        get("BACKREST_REPOSITORY_PASSWORD") != password
        or run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                "restic",
                "-s",
                service,
                "-w",
            ]
        ).stdout.removesuffix("\n")
        != password
    ):
        raise RuntimeError("Independent repository key verification failed")
    admin = get("BACKREST_ADMIN_PASSWORD")
    if admin is None:
        admin = secrets.token_urlsafe(36)
        save("BACKREST_ADMIN_PASSWORD", admin)
    encoded = get("BACKREST_ADMIN_PASSWORD_BCRYPT")
    if encoded is None:
        encoded = base64.b64encode(
            bcrypt.hashpw(admin.encode(), bcrypt.gensalt(rounds=12))
        ).decode()
        save("BACKREST_ADMIN_PASSWORD_BCRYPT", encoded)
    if not bcrypt.checkpw(admin.encode(), base64.b64decode(encoded, validate=True)):
        raise RuntimeError(
            "Existing UI password/hash mismatch; no automatic reset attempted"
        )
    print(
        json.dumps(
            {
                "cluster": cluster,
                "credentials_verified": True,
                "keychain_service": service,
                "ui_user": "admin",
                "ui_password_item": "BACKREST_ADMIN_PASSWORD",
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=["app-cluster", "infra-cluster"])
    args = parser.parse_args()
    try:
        bootstrap(args.cluster)
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(1, f"ERROR: {error}\n")
