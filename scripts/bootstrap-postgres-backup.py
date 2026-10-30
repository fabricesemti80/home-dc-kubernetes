#!/usr/bin/env python3
"""Provision a marked read-only backup login without rotating application users."""

import argparse
import base64
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "app-cluster": {
        "config": "apps",
        "namespace": "media",
        "selector": "app.kubernetes.io/instance=immich,app.kubernetes.io/controller=database",
        "secret": "IMMICH_BACKUP_PASSWORD",
        "kubeconfig": ROOT / "kubeconfig",
    },
    "infra-cluster": {
        "config": "infra",
        "namespace": "ai",
        "selector": "app.kubernetes.io/instance=litellm-postgres,app.kubernetes.io/name=postgres",
        "secret": "LITELLM_BACKUP_PASSWORD",
        "kubeconfig": ROOT / ".private/infra-cluster/kubeconfig",
    },
}


def captured(args, value=None):
    result = subprocess.run(
        args, input=value, text=True, capture_output=True, timeout=45
    )
    if result.returncode:
        raise RuntimeError(
            f"{args[0]} operation failed; credential-bearing diagnostics suppressed"
        )
    return result.stdout


def scram(password):
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    stored = hashlib.sha256(hmac.digest(salted, b"Client Key", "sha256")).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")
    encode = lambda value: base64.b64encode(value).decode()
    return f"SCRAM-SHA-256$4096:{encode(salt)}${encode(stored)}:{encode(server)}"


def bootstrap(cluster):
    source = SOURCES[cluster]
    common = ["--project", "home-dc-kubernetes", "--config", source["config"]]
    key = source["secret"]
    names = json.loads(
        captured(["doppler", "secrets", *common, "--only-names", "--json"])
    )
    if key in names:
        password = json.loads(
            captured(["doppler", "secrets", "get", key, *common, "--json"])
        )[key]["computed"]
    else:
        password = secrets.token_urlsafe(48)
        captured(
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
            password,
        )
    if not isinstance(password, str) or not password:
        raise RuntimeError(
            "Backup login password is empty/non-string; no database principal changed"
        )
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(source["kubeconfig"]),
        "-n",
        source["namespace"],
    ]
    pods = json.loads(
        captured(kubectl + ["get", "pods", "-l", source["selector"], "-o", "json"])
    )["items"]
    ready = [
        p
        for p in pods
        if any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in p["status"].get("conditions", [])
        )
    ]
    if len(ready) != 1:
        raise RuntimeError(
            "Expected exactly one ready source database; no database principal changed"
        )
    pod = ready[0]["metadata"]["name"]
    marker = f"home-dc-kubernetes/{cluster}/{source['namespace']}/postgres-backup"
    verifier = scram(password)
    sql = rf"""DO $bootstrap$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='k8up_backup') THEN
  IF (SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname='k8up_backup') IS DISTINCT FROM '{marker}' THEN
   RAISE EXCEPTION 'Refusing to modify a backup role not owned by this bootstrap';
  END IF;
 ELSE
  CREATE ROLE k8up_backup LOGIN;
 END IF;
END $bootstrap$;
COMMENT ON ROLE k8up_backup IS '{marker}';
ALTER ROLE k8up_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '{verifier}';
GRANT pg_read_all_data, pg_read_all_settings TO k8up_backup;
SELECT format('GRANT CONNECT ON DATABASE %I TO k8up_backup',current_database()) \gexec
"""
    shell = 'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
    captured(kubectl + ["exec", "-i", pod, "--", "sh", "-ec", shell], sql)
    verify = """IFS= read -r PGPASSWORD
export PGPASSWORD
psql -X -h 127.0.0.1 -U k8up_backup -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atc "SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND rolcanlogin AND pg_has_role(current_user,'pg_read_all_data','MEMBER') AND pg_has_role(current_user,'pg_read_all_settings','MEMBER') FROM pg_roles WHERE rolname=current_user"
"""
    if (
        captured(
            kubectl + ["exec", "-i", pod, "--", "sh", "-ec", verify], password + "\n"
        ).strip()
        != "t"
    ):
        raise RuntimeError("Backup login authentication/least-privilege check failed")
    print(
        f"PASS {cluster}: dedicated k8up_backup login authenticated with read-all-data/CONNECT and no superuser/create/replication/RLS-bypass privileges; application credentials unchanged"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cluster", choices=SOURCES)
    args = parser.parse_args()
    try:
        bootstrap(args.cluster)
    except (
        RuntimeError,
        subprocess.TimeoutExpired,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
