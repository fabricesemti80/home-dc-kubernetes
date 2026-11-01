#!/usr/bin/env python3
"""Create or validate scoped mTLS identities for monitoring connections."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SERVER_IP = "10.0.40.107"
PROFILES = {
    "remote-write": {
        "server_ip": SERVER_IP,
        "client_name": "app-cluster-vmagent",
        "keys": {
            ("home-dc-kubernetes", "infra"): {
                "MONITORING_REMOTE_CA_CERT": "ca.crt",
                "MONITORING_REMOTE_SERVER_CERT": "server.crt",
                "MONITORING_REMOTE_SERVER_KEY": "server.key",
            },
            ("home-dc-kubernetes", "apps"): {
                "MONITORING_REMOTE_CA_CERT": "client-ca.crt",
                "MONITORING_REMOTE_CLIENT_CERT": "client.crt",
                "MONITORING_REMOTE_CLIENT_KEY": "client.key",
            },
        },
    },
    "pve-hardware": {
        "server_ip": "10.0.40.10",
        "client_name": "infra-vmagent",
        "keys": {
            ("home-dc-proxmox", "prd"): {
                "MONITORING_HW_CA_CERT": "ca.crt",
                "MONITORING_HW_SERVER_CERT": "server.crt",
                "MONITORING_HW_SERVER_KEY": "server.key",
            },
            ("home-dc-kubernetes", "infra"): {
                "MONITORING_HW_CA_CERT": "client-ca.crt",
                "MONITORING_HW_CLIENT_CERT": "client.crt",
                "MONITORING_HW_CLIENT_KEY": "client.key",
            },
        },
    },
}


def run(args, *, data=None):
    result = subprocess.run(args, input=data, text=True, capture_output=True, timeout=60)
    if result.returncode:
        # Do not emit stdout/stderr, which can contain secret material.
        raise RuntimeError(f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout


def doppler(project, config, *args, data=None):
    return run(["doppler", *args, "--project", project, "--config", config, "--no-check-version"], data=data)


def validate(directory, server_ip=SERVER_IP):
    ca = directory / "ca.crt"
    if ca.read_bytes() != (directory / "client-ca.crt").read_bytes():
        raise RuntimeError("Monitoring CA certificates differ between scopes")
    for name in ("server", "client"):
        cert = directory / f"{name}.crt"
        key = directory / f"{name}.key"
        run(["openssl", "verify", "-x509_strict", "-purpose", "sslserver" if name == "server" else "sslclient", "-CAfile", str(ca), str(cert)])
        run(["openssl", "x509", "-in", str(cert), "-noout", "-checkend", "2592000"])
        public_from_cert = run(["openssl", "x509", "-in", str(cert), "-pubkey", "-noout"])
        public_from_key = run(["openssl", "pkey", "-in", str(key), "-pubout"])
        if public_from_cert != public_from_key:
            raise RuntimeError(f"Monitoring {name} certificate does not match its private key")
    decoded = subprocess.run(["openssl", "x509", "-in", str(directory / "server.crt"), "-noout", "-text"], capture_output=True, text=True, check=True, timeout=30).stdout
    if f"IP Address:{server_ip}" not in decoded:
        raise RuntimeError("Monitoring server certificate lacks the expected IP SAN")


def generate(directory, server_ip=SERVER_IP, client_name="app-cluster-vmagent", purpose="remote-write"):
    # The CA private key is temporary and never copied into either Doppler config.
    ca_conf = directory / "ca.cnf"
    ca_conf.write_text(f"[req]\ndistinguished_name=dn\nprompt=no\nx509_extensions=ca\n[dn]\nCN=home-dc-monitoring-{purpose}-ca\n[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n")
    run(["openssl", "req", "-new", "-x509", "-newkey", "rsa:3072", "-nodes", "-days", "1825", "-config", str(ca_conf), "-keyout", str(directory / "ca.key"), "-out", str(directory / "ca.crt")])
    for name, usage, san in (("server", "serverAuth", f"IP:{server_ip}"), ("client", "clientAuth", f"DNS:{client_name}")):
        ext = directory / f"{name}.ext"
        ext.write_text(f"[cert]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage={usage}\nsubjectAltName={san}\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n")
        run(["openssl", "req", "-new", "-newkey", "rsa:3072", "-nodes", "-subj", f"/CN=monitoring-{name}", "-keyout", str(directory / f"{name}.key"), "-out", str(directory / f"{name}.csr")])
        run(["openssl", "x509", "-req", "-in", str(directory / f"{name}.csr"), "-CA", str(directory / "ca.crt"), "-CAkey", str(directory / "ca.key"), "-CAcreateserial", "-days", "365", "-sha256", "-extfile", str(ext), "-extensions", "cert", "-out", str(directory / f"{name}.crt")])
    (directory / "client-ca.crt").write_bytes((directory / "ca.crt").read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="remote-write")
    parser.add_argument("--apply", action="store_true", help="Create credentials only when all are absent")
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    found = {}
    for (project, config), keys in profile["keys"].items():
        names = json.loads(doppler(project, config, "secrets", "--only-names", "--json"))
        found[(project, config)] = set(keys) & set(names)
    total = sum(map(len, found.values()))
    required = sum(map(len, profile["keys"].values()))
    if total not in (0, required):
        raise RuntimeError("Partial monitoring PKI exists in Doppler; inspect and reconcile it manually before retrying")
    with tempfile.TemporaryDirectory(prefix="monitoring-remote-pki-") as tmp:
        directory = Path(tmp)
        if total:
            for (project, config), keys in profile["keys"].items():
                for name, filename in keys.items():
                    (directory / filename).write_text(doppler(project, config, "secrets", "get", name, "--plain"))
            validate(directory, profile["server_ip"])
            print(f"Monitoring {args.profile} PKI is complete, valid for at least 30 days and unchanged.")
            return
        if not args.apply:
            print(f"Monitoring {args.profile} PKI is absent; apply creates separate server/client identities in Doppler.")
            return
        generate(directory, profile["server_ip"], profile["client_name"], args.profile)
        validate(directory, profile["server_ip"])
        try:
            for (project, config), keys in profile["keys"].items():
                for name, filename in keys.items():
                    doppler(project, config, "secrets", "set", name, "--no-interactive", data=(directory / filename).read_text())
        except Exception as exc:
            raise RuntimeError("PKI storage was interrupted; inspect Doppler key presence and reconcile partial state manually") from exc
        print(f"Stored scoped monitoring {args.profile} PKI in Doppler; temporary CA private key discarded.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
