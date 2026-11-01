#!/usr/bin/env python3
"""Inventory and retire Pulse workloads after GitOps removes their Applications.

Never removes namespaces, volumes, host data, secrets, or Doppler credentials.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ["kubectl", "--kubeconfig", str(ROOT / "kubeconfig")]
INFRA = ["kubectl", "--kubeconfig", str(ROOT / ".private/infra-cluster/kubeconfig")]
INVENTORY = ROOT / ".private/pulse-retirement/inventory.json"
APPS = ("pulse-infra", "pulse-agent-infra")
# Explicit allowlist. Credential resources and the shared namespace are preserved.
ALLOWED = {
    ("", "ConfigMap", "monitoring", "pulse-system-config"),
    ("", "Service", "monitoring", "pulse"),
    ("apps", "Deployment", "monitoring", "pulse"),
    ("gateway.networking.k8s.io", "HTTPRoute", "monitoring", "pulse"),
    ("gateway.networking.k8s.io", "HTTPRoute", "monitoring", "pulse-internal"),
    ("", "ServiceAccount", "monitoring", "pulse-agent"),
    ("apps", "DaemonSet", "monitoring", "pulse-agent"),
    ("rbac.authorization.k8s.io", "ClusterRole", "", "pulse-agent"),
    ("rbac.authorization.k8s.io", "ClusterRoleBinding", "", "pulse-agent"),
}


def get(command, resource, name, namespace=""):
    args = command + ["get", resource, name, "--ignore-not-found", "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    result = subprocess.run(args, check=True, capture_output=True, text=True).stdout
    return json.loads(result) if result.strip() else None


def resource_type(item):
    group, kind, _, _ = item
    return kind + ("." + group if group else "")


def identity(command, resource, name, namespace=""):
    obj = get(command, resource, name, namespace)
    if obj is None:
        raise RuntimeError(f"Missing {resource} {namespace}/{name}")
    return obj["metadata"]["uid"]


def prepare():
    apps = {}
    resources = {}
    for name in APPS:
        app = get(HUB, "applications.argoproj.io", name, "argo-system")
        if not app or app["metadata"].get("finalizers") or app["spec"]["destination"].get("name") != "infra-cluster":
            raise RuntimeError(f"Unsafe or missing Application {name}")
        apps[name] = app["metadata"]["uid"]
        for item in app.get("status", {}).get("resources", []):
            key = tuple(item.get(field, "") for field in ("group", "kind", "namespace", "name"))
            if key not in ALLOWED:
                if key[1] not in {"Namespace", "DopplerSecret"}:
                    raise RuntimeError(f"Unexpected tracked resource {key}")
                continue
            obj = get(INFRA, resource_type(key), key[3], key[2])
            if not obj:
                raise RuntimeError(f"Tracked resource missing: {key}")
            resources["|".join(key)] = {"uid": obj["metadata"]["uid"], "app": name}
    if set(resources) != {"|".join(key) for key in ALLOWED}:
        raise RuntimeError("Pulse resource inventory is incomplete")
    data = {"cluster_uid": identity(INFRA, "namespace", "kube-system"), "apps": apps, "resources": resources}
    INVENTORY.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(INVENTORY.parent, 0o700)
    fd = os.open(INVENTORY, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"Saved {INVENTORY}; no live resources changed.")


def inventory():
    data = json.loads(INVENTORY.read_text())
    if data["cluster_uid"] != identity(INFRA, "namespace", "kube-system") or set(data["apps"]) != set(APPS):
        raise RuntimeError("Cluster identity or Application inventory changed")
    if set(data["resources"]) != {"|".join(key) for key in ALLOWED}:
        raise RuntimeError("Resource allowlist differs from inventory")
    return data


def unregister():
    data = inventory()
    parent = get(HUB, "applications.argoproj.io", "apps", "argo-system")
    prunable = {r["name"] for r in parent.get("status", {}).get("resources", []) if r.get("kind") == "Application" and r.get("requiresPruning") is True}
    for name in APPS:
        app = get(HUB, "applications.argoproj.io", name, "argo-system")
        if not app or name not in prunable or app["metadata"]["uid"] != data["apps"][name] or app["metadata"].get("finalizers") or app["spec"]["destination"].get("name") != "infra-cluster":
            raise RuntimeError(f"Application {name} is not the inventoried, safely prunable instance")
    subprocess.run(HUB + ["-n", "argo-system", "delete", "applications.argoproj.io", *APPS, "--cascade=orphan", "--wait=true"], check=True)
    print("Applications unregistered without cascading; data and credentials preserved.")


def remove():
    data = inventory()
    for name in APPS:
        if get(HUB, "applications.argoproj.io", name, "argo-system"):
            raise RuntimeError(f"Application {name} is still registered")
    namespace = get(INFRA, "namespace", "monitoring")
    tracking = namespace["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
    if not tracking.startswith("uptime-kuma-infra:"):
        raise RuntimeError("Shared monitoring namespace has not transferred to uptime-kuma-infra")
    if get(INFRA, "cronjob", "protect-pulse", "monitoring"):
        raise RuntimeError("Pulse capture CronJob is still present")
    config = subprocess.run(
        INFRA + ["-n", "backups", "exec", "deployment/backrest", "--", "cat", "/state/config.json"],
        check=True, capture_output=True, text=True,
    )
    if any(plan.get("id") == "app-pulse" for plan in json.loads(config.stdout).get("plans", [])):
        raise RuntimeError("The live Backrest configuration still contains app-pulse")
    # Verify every remaining UID and Argo owner before performing any deletion.
    pending = []
    for serialized, expected in data["resources"].items():
        key = tuple(serialized.split("|"))
        obj = get(INFRA, resource_type(key), key[3], key[2])
        if obj is None:
            continue
        annotations = obj["metadata"].get("annotations", {})
        if obj["metadata"]["uid"] != expected["uid"] or not annotations.get("argocd.argoproj.io/tracking-id", "").startswith(expected["app"] + ":"):
            raise RuntimeError(f"Resource identity or owner changed: {key}")
        pending.append(key)
    for key in pending:
        args = INFRA + ["delete", resource_type(key), key[3], "--wait=true", "--timeout=300s"]
        if key[2]:
            args += ["-n", key[2]]
        subprocess.run(args, check=True)
    print("Pulse workloads removed; shared namespace, credentials, backups and /var/pulse/data preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "unregister", "remove"))
    args = parser.parse_args()
    {"prepare": prepare, "unregister": unregister, "remove": remove}[args.action]()
