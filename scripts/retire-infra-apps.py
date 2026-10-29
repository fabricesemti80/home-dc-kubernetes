#!/usr/bin/env python3
"""Inventory, then remove orphaned Kestra and KubeVirt resources after GitOps removal."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ["kubectl", "--kubeconfig", str(ROOT / "kubeconfig")]
INFRA = ["kubectl", "--kubeconfig", str(ROOT / ".private/infra-cluster/kubeconfig")]
INVENTORY = ROOT / ".private/infra-retirement/inventory.json"
# Runtime CRs must finish deleting while their operators are still present.
ORDER = ["kubevirt-manager-infra", "kubevirt-runtime-infra", "kubevirt-operators-infra", "kestra-infra"]
NAMESPACES = ["kestra", "kubevirt", "kubevirt-manager", "kubevirt-lab", "cdi"]
PRESERVE = {"Namespace", "PersistentVolume", "PersistentVolumeClaim"}
GUEST_RESOURCES = [
    "virtualmachines.kubevirt.io",
    "virtualmachineinstances.kubevirt.io",
    "virtualmachinepools.pool.kubevirt.io",
    "datavolumes.cdi.kubevirt.io",
]


def output(command):
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def get(command, resource, *args):
    value = output(command + ["get", resource, *args, "-o", "json"])
    return json.loads(value) if value.strip() else None


def no_guests():
    crds = {item["metadata"]["name"] for item in get(INFRA, "crds")["items"]}
    for resource in GUEST_RESOURCES:
        if resource in crds and get(INFRA, resource, "-A")["items"]:
            raise RuntimeError(f"Refusing retirement: {resource} still exist")


def retained_claims():
    claims = [item for item in get(INFRA, "pvc", "-A")["items"] if item["metadata"]["namespace"] in NAMESPACES]
    for item in get(INFRA, "statefulsets", "-A")["items"]:
        if item["metadata"]["namespace"] in NAMESPACES and item["spec"].get("persistentVolumeClaimRetentionPolicy", {}).get("whenDeleted", "Retain") != "Retain":
            raise RuntimeError(f"StatefulSet {item['metadata']['name']} would delete its PVCs")
    for claim in claims:
        volume = claim["spec"].get("volumeName")
        if not volume or get(INFRA, "pv", volume)["spec"]["persistentVolumeReclaimPolicy"] != "Retain":
            raise RuntimeError(f"PVC {claim['metadata']['namespace']}/{claim['metadata']['name']} lacks a bound Retain PV")
    return [{"namespace": item["metadata"]["namespace"], "name": item["metadata"]["name"], "volume": item["spec"]["volumeName"]} for item in claims]


def cluster_uid():
    return get(INFRA, "namespace", "kube-system")["metadata"]["uid"]


def prepare():
    no_guests()
    claims = retained_claims()
    apps = {}
    for name in ORDER:
        app = get(APP, "application.argoproj.io", name, "-n", "argo-system")
        if app["metadata"].get("finalizers"):
            raise RuntimeError(f"{name} has cascading finalizers; review before removing its Git registration")
        if app["spec"]["destination"].get("name") != "infra-cluster":
            raise RuntimeError(f"Unexpected destination for {name}")
        resources = app.get("status", {}).get("resources", [])
        if not resources:
            raise RuntimeError(f"No tracked resource inventory for {name}")
        apps[name] = [{key: resource.get(key, "") for key in ("group", "kind", "namespace", "name")} for resource in resources]
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(INVENTORY.parent, 0o700)
    inventory = {"infra_cluster_uid": cluster_uid(), "applications": apps, "retained_claims": claims}
    fd = os.open(INVENTORY, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(inventory, handle, indent=2)
        handle.write("\n")
    print(f"Saved private inventory: {INVENTORY}")
    print(f"No guests/imports; preserving {len(claims)} PVCs and all involved namespaces. No live resources changed.")
    print("Merge the removal PR, wait for the four child Applications to disappear, then run the retire-infra task.")


def remove():
    inventory = json.loads(INVENTORY.read_text())
    if inventory["infra_cluster_uid"] != cluster_uid():
        raise RuntimeError("Infra cluster identity differs from the prepared inventory")
    if set(inventory["applications"]) != set(ORDER):
        raise RuntimeError("Incomplete or unexpected prepared Application inventory")
    # Orphaned apps are intentional: never cascade-delete their data-bearing namespaces.
    for name in ORDER:
        if get(APP, "application.argoproj.io", name, "-n", "argo-system", "--ignore-not-found"):
            raise RuntimeError(f"{name} still registered: merge and let the parent reconcile before retirement")
    no_guests()
    retained_claims()
    for name in ORDER:
        print(f"Retiring tracked resources: {name}", flush=True)
        resources = inventory["applications"][name]
        # CRDs last within each application; deleting runtime CRs in the previous
        # application waits for their operator finalizers before operators are removed.
        resources = sorted(resources, key=lambda item: item["kind"] == "CustomResourceDefinition")
        for resource in resources:
            if resource["kind"] in PRESERVE:
                continue
            if resource["group"] in {"kubevirt.io", "cdi.kubevirt.io"}:
                crds = get(INFRA, "crds")["items"]
                if not any(item["spec"]["group"] == resource["group"] and item["spec"]["names"]["kind"] == resource["kind"] for item in crds):
                    print(f"Already uninstalled API: {resource['kind']}.{resource['group']}")
                    continue
            resource_type = resource["kind"] + ("." + resource["group"] if resource["group"] else "")
            command = INFRA + ["delete", resource_type, resource["name"], "--ignore-not-found", "--wait=true", "--timeout=300s"]
            if resource["namespace"]:
                command += ["-n", resource["namespace"]]
            subprocess.run(command, check=True)
    for claim in inventory["retained_claims"]:
        current = get(INFRA, "pvc", claim["name"], "-n", claim["namespace"])
        if current["spec"]["volumeName"] != claim["volume"]:
            raise RuntimeError(f"Retained PVC binding changed: {claim['namespace']}/{claim['name']}")
    remaining = []
    for item in get(INFRA, "crds")["items"]:
        group = item["spec"]["group"]
        if group == "kubevirt.io" or group.endswith(".kubevirt.io") or group == "kubevirt-manager.io":
            remaining.append(item["metadata"]["name"])
    for item in get(INFRA, "pods", "-A")["items"]:
        if item["metadata"]["namespace"] in NAMESPACES and item["status"]["phase"] not in {"Succeeded", "Failed"}:
            remaining.append(f"{item['metadata']['namespace']}/{item['metadata']['name']}")
    for kind in ("mutatingwebhookconfigurations", "validatingwebhookconfigurations"):
        for item in get(INFRA, kind)["items"]:
            name = item["metadata"]["name"]
            if name.startswith(("virt-", "kubevirt-", "cdi-")):
                remaining.append(f"{kind}/{name}")
    if remaining:
        raise RuntimeError("Retirement left resources requiring inspection (do not force finalizers): " + ", ".join(remaining))
    print("Retired Kestra/KubeVirt resources; no remaining runtime pods, CRDs or webhooks. Namespaces, PVCs and NAS data preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "remove"])
    args = parser.parse_args()
    try:
        prepare() if args.action == "prepare" else remove()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
