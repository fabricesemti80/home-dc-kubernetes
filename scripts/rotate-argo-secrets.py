#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["bcrypt==5.0.0"]
# ///
"""Rotate the Argo CD admin password and GitHub webhook secret.

rotate       Generate both values, write them SOPS-encrypted to the Argo values
             file, and refresh the local template inputs (cluster.yaml
             argo_password, github-push-token.txt). Prints the admin password once.
sync-webhook Read the current webhook secret from the encrypted values file and
             set it on the GitHub repository webhook. Run after Argo CD syncs.

Secret values never go into argv or logs. They are passed through stdin or temp files.
"""

import argparse
import datetime
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[1]
VALUES = Path("kubernetes/apps/app-cluster/argo-system/argo-cd/values.sops.yaml")
REPO = "fabricesemti80/home-dc-kubernetes"
WEBHOOK_PATH = "/api/webhook"


def run(argv, *, data=None):
    result = subprocess.run(argv, input=data, text=True, capture_output=True, cwd=ROOT, timeout=120)
    if result.returncode:
        # Suppress output: it may contain secret material.
        sys.exit(f"{argv[0]} {argv[1] if len(argv) > 1 else ''} failed (exit {result.returncode})")
    return result.stdout


def require(*tools):
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        sys.exit(f"missing tools: {', '.join(missing)}")
    key = os.environ.get("SOPS_AGE_KEY_FILE", str(ROOT / "age.key"))
    if "sops" in tools and not Path(key).is_file():
        sys.exit(f"age key not found at {key}; run inside the repo dev shell")


def rotate(_args):
    require("sops")
    password = secrets.token_urlsafe(24)
    # Argo uses Go bcrypt; the $2a prefix matches the documented htpasswd recipe.
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()
    hashed = "$2a$" + hashed[4:]
    webhook = secrets.token_hex(32)
    # RFC3339: Argo only honours a parseable mtime, which revokes sessions issued before it.
    mtime = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    plaintext = (
        'fullnameOverride: "argocd"\n'
        "configs:\n"
        "  secret:\n"
        f"    argocdServerAdminPassword: {json.dumps(hashed)}\n"
        f"    argocdServerAdminPasswordMtime: {json.dumps(mtime)}\n"
        f"    githubSecret: {json.dumps(webhook)}\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        os.chmod(tmp.name, 0o600)
        tmp.write(plaintext)
    try:
        encrypted = run(["sops", "--encrypt", "--filename-override", str(VALUES),
                         "--input-type", "yaml", "--output-type", "yaml", tmp.name])
    finally:
        os.unlink(tmp.name)
    if "ENC[" not in encrypted.split("sops:")[0]:
        sys.exit("sops did not encrypt the secret keys; check the .sops.yaml rule order")
    (ROOT / VALUES).write_text(encrypted)

    # Keep local template inputs in step so `task configure` doesn't revert the rotation.
    token_file = ROOT / "github-push-token.txt"
    token_file.write_text(webhook + "\n")
    token_file.chmod(0o600)
    cluster = ROOT / "cluster.yaml"
    if cluster.is_file():
        text = cluster.read_text()
        new, count = re.subn(r"(?m)^argo_password:.*$", lambda _: f"argo_password: {json.dumps(hashed)}", text)
        if count:
            cluster.write_text(new)

    print(f"Rotated {VALUES} (encrypted). Updated github-push-token.txt"
          + (" and cluster.yaml argo_password." if cluster.is_file() else "."))
    print("\nNew Argo CD admin password (shown once, store it in your password manager):\n")
    print(f"    {password}\n")
    print("Next: commit the values file, merge, wait for Argo CD to sync, then run\n"
          "    task secrets:argo-sync-webhook")


def sync_webhook(_args):
    require("sops", "gh")
    secret = run(["sops", "--decrypt", "--extract", '["configs"]["secret"]["githubSecret"]', str(VALUES)]).strip()
    if not secret:
        sys.exit("githubSecret is empty")
    hooks = json.loads(run(["gh", "api", f"repos/{REPO}/hooks"]))
    matches = [h for h in hooks if WEBHOOK_PATH in h.get("config", {}).get("url", "")]
    if len(matches) != 1:
        sys.exit(f"expected one Argo webhook on {REPO}, found {len(matches)}")
    hook = matches[0]
    run(["gh", "api", "-X", "PATCH", f"repos/{REPO}/hooks/{hook['id']}/config", "--input", "-"],
        data=json.dumps({"secret": secret}))
    print(f"Updated secret on webhook {hook['id']} ({hook['config']['url']}).")
    print("Check a delivery in GitHub → Settings → Webhooks → Recent Deliveries returns 200.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(required=True)
    sub.add_parser("rotate").set_defaults(func=rotate)
    sub.add_parser("sync-webhook").set_defaults(func=sync_webhook)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
