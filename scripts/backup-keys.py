#!/usr/bin/env python3
"""Bootstrap/verify repository passwords in Doppler and independent macOS Keychain."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    "app-cluster": {"media": {"critical-6h"}},
    "infra-cluster": {"ai": {"critical-6h"}},
}


def command(args, value=None):
    """Never return child credential output through an exception or the console."""
    result = subprocess.run(
        args, input=value, text=True, capture_output=True, timeout=45
    )
    if result.returncode:
        raise RuntimeError(
            f"Credential operation failed: {args[0]} {args[1]}; output suppressed"
        )
    return result.stdout


def escrow(service):
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
    if result.returncode == 44:
        return None
    if result.returncode:
        raise RuntimeError(
            "Cannot read Keychain escrow; unlock/authorize the default keychain"
        )
    value = result.stdout.removesuffix("\n")
    if not value:
        raise RuntimeError(
            "Existing escrow is empty; refusing to replace it automatically"
        )
    return value


def save_escrow(service, value):
    # security's interactive interpreter consumes this through stdin, not argv.
    line = f"add-generic-password -a restic -s {service} -T /usr/bin/security -X {value.encode().hex()}\n"
    command(["/usr/bin/security", "-i"], line)
    if escrow(service) != value:
        raise RuntimeError(
            "Keychain escrow verification failed; no repository should be initialized"
        )


def require_empty_repository(cluster, namespace, profile):
    # Missing credential stores are not permission to replace an existing key.
    from backup_apps import Resources, RESTIC_IMAGE
    from k8up_pilot import SECURITY, CONTAINER_SECURITY

    resources = Resources(cluster, "backups")
    try:
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": resources.name},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": SECURITY,
                    "containers": [
                        {
                            "name": "inspect",
                            "image": RESTIC_IMAGE,
                            "command": [
                                "sh",
                                "-ec",
                                'test -r "$2"; test -x "$2"; if [ -e "$3" ]; then test -d "$3"; test -r "$3"; test -x "$3"; fi; test ! -L "$1"; if [ -e "$1" ]; then test -d "$1"; entries=$(find "$1" -mindepth 1 -maxdepth 1 -print -quit); test -z "$entries"; fi',
                                "--",
                                f"/repository/{cluster}/{namespace}/{profile}",
                                f"/repository/{cluster}",
                                f"/repository/{cluster}/{namespace}",
                            ],
                            "securityContext": CONTAINER_SECURITY,
                            "resources": {
                                "requests": {"cpu": "10m", "memory": "16Mi"},
                                "limits": {"cpu": "100m", "memory": "32Mi"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "repository",
                                    "mountPath": "/repository",
                                    "readOnly": True,
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "repository",
                            "nfs": {
                                "server": "10.0.40.2",
                                "path": "/k8s-backup",
                                "readOnly": True,
                            },
                        }
                    ],
                },
            }
        )
        resources.call(
            "wait",
            "--for=jsonpath={.status.containerStatuses[0].state.terminated.exitCode}",
            "pod/" + resources.name,
            "--timeout=90s",
        )
        pod = resources.get("pod", resources.name)
        if pod["status"]["containerStatuses"][0]["state"]["terminated"]["exitCode"]:
            raise RuntimeError(
                "Repository is nonempty or unreadable; recover its existing key, never initialize a replacement"
            )
    finally:
        resources.cleanup()


def bootstrap(args):
    if (
        args.namespace not in POLICIES[args.cluster]
        or args.profile not in POLICIES[args.cluster][args.namespace]
    ):
        raise RuntimeError("Unsupported cluster/namespace/profile combination")
    if not Path("/usr/bin/security").is_file():
        raise RuntimeError(
            "This bootstrap requires the administrator macOS Keychain; do not generate unescrowed keys"
        )
    config = "apps" if args.cluster == "app-cluster" else "infra"
    key = f"K8UP_{args.namespace}_{args.profile}_PASSWORD".upper().replace("-", "_")
    service = f"home-dc.backups.{args.cluster}.{args.namespace}.{args.profile}"
    common = ["--project", "home-dc-kubernetes", "--config", config]
    names = json.loads(
        command(["doppler", "secrets", *common, "--only-names", "--json"])
    )
    primary = None
    if key in names:
        data = json.loads(
            command(["doppler", "secrets", "get", key, *common, "--json"])
        )
        primary = data[key]["computed"]
        if not isinstance(primary, str) or not primary:
            raise RuntimeError(
                "Existing Doppler key is empty/non-string; refusing automatic replacement"
            )
    recovery = escrow(service)
    if primary is not None and recovery is not None and primary != recovery:
        raise RuntimeError(
            "Doppler/Keychain mismatch: preserve both copies and inspect repository history; no key changed"
        )
    if args.action == "verify":
        if primary is None or recovery is None:
            raise RuntimeError(
                "Repository key is not present in both Doppler and Keychain"
            )
    else:
        if primary is None and recovery is None:
            require_empty_repository(args.cluster, args.namespace, args.profile)
        value = (
            primary
            if primary is not None
            else recovery if recovery is not None else secrets.token_urlsafe(48)
        )
        if recovery is None:
            save_escrow(service, value)
        if primary is None:
            command(
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
        check = json.loads(
            command(["doppler", "secrets", "get", key, *common, "--json"])
        )[key]["computed"]
        if check != value or escrow(service) != value:
            raise RuntimeError(
                "Repository key round-trip mismatch; do not enroll sources"
            )
    print(
        json.dumps(
            {
                "result": "verified",
                "cluster": args.cluster,
                "namespace": args.namespace,
                "profile": args.profile,
                "doppler_project": "home-dc-kubernetes",
                "doppler_config": config,
                "doppler_secret": key,
                "keychain_service": service,
                "keychain_account": "restic",
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "verify"])
    parser.add_argument("cluster", choices=POLICIES)
    parser.add_argument("namespace")
    parser.add_argument("profile")
    args = parser.parse_args()
    lock_dir = ROOT / ".private"
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(lock_dir / "backup-key-bootstrap.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        bootstrap(args)
    except (
        RuntimeError,
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        KeyError,
    ) as error:
        parser.exit(1, f"ERROR: {error}\n")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
