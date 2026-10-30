#!/usr/bin/env python3
"""Bootstrap and verify the two GitOps-managed K8up installations."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/fabricesemti80/home-dc-kubernetes.git"
HUB = ["kubectl", "--kubeconfig", str(ROOT / "kubeconfig")]
TARGETS = {
    "app-cluster": ("app", ROOT / "kubeconfig"),
    "infra-cluster": ("infra", ROOT / ".private/infra-cluster/kubeconfig"),
}
CRDS = [f"{name}.k8up.io" for name in (
    "archives", "backups", "checks", "podconfigs", "prebackuppods",
    "prunes", "restores", "schedules", "snapshots",
)]


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def get_json(command):
    return json.loads(run(command + ["-o", "json"], capture_output=True).stdout)


def values(cluster):
    path = ROOT / f"kubernetes/apps/{cluster}/storage/k8up/values.yaml"
    return json.loads(run(["yq", "-o=json", ".", str(path)], capture_output=True).stdout)


def verify(cluster, expect_idle):
    _, kubeconfig = TARGETS[cluster]
    kubectl = ["kubectl", "--kubeconfig", str(kubeconfig)]
    run(kubectl + ["wait", "--for=condition=Established", *[f"crd/{name}" for name in CRDS], "--timeout=180s"])
    run(kubectl + ["-n", "backups", "rollout", "status", "deployment/k8up", "--timeout=180s"])
    deployment = get_json(kubectl + ["-n", "backups", "get", "deployment", "k8up"])
    expected = values(cluster)
    image = expected["image"]
    image_ref = f"{image['registry']}/{image['repository']}:{image['tag']}"
    container = next(c for c in deployment["spec"]["template"]["spec"]["containers"] if c["name"] == "k8up-operator")
    env = {item["name"]: item.get("value") for item in container["env"]}
    if container["image"] != image_ref or env.get("BACKUP_IMAGE") != image_ref:
        raise RuntimeError("Operator or runner image differs from the reviewed digest pin")
    if env.get("BACKUP_SKIP_WITHOUT_ANNOTATION") != "true" or env.get("TZ") != "UTC":
        raise RuntimeError("Operator must use opt-in-only discovery and UTC")
    if deployment["spec"]["template"]["spec"].get("nodeSelector") != expected["nodeSelector"]:
        raise RuntimeError("Operator node placement differs from declared configuration")
    for name in CRDS:
        crd = get_json(kubectl + ["get", "crd", name])
        options = set(crd["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-options", "").split(","))
        if not {"Prune=false", "Delete=false"} <= options:
            raise RuntimeError(f"CRD lacks lifecycle protection: {name}")
    services = get_json(kubectl + ["-n", "backups", "get", "services", "-l", "app.kubernetes.io/instance=k8up"])
    metrics = [service for service in services["items"] if any(port["port"] == 8080 for port in service["spec"]["ports"])]
    if len(metrics) != 1:
        raise RuntimeError("Expected exactly one internal K8up metrics service")
    name = metrics[0]["metadata"]["name"]
    endpoint = f"/api/v1/namespaces/backups/services/http:{name}:8080/proxy/metrics"
    text = run(kubectl + ["get", "--raw", endpoint], capture_output=True).stdout
    if "go_goroutines " not in text or "process_start_time_seconds " not in text:
        raise RuntimeError("Controller metrics endpoint did not return expected Go process metrics")
    counts = {}
    for kind in ("schedules", "backups", "restores", "prunes"):
        counts[kind] = len(get_json(kubectl + ["get", f"{kind}.k8up.io", "-A"])["items"])
    if expect_idle and any(counts.values()):
        raise RuntimeError(f"Expected idle operator-only rollout, found policy/operation resources: {counts}")
    print(f"PASS {cluster}: protected CRDs, digest-pinned operator/runner, worker placement, opt-in, UTC and live metrics")
    print(f"Current K8up operation counts: {json.dumps(counts, sort_keys=True)}")


def bootstrap(cluster, revision):
    suffix, _ = TARGETS[cluster]
    path = ROOT / f"kubernetes/argo/apps/{cluster}/storage/k8up.yaml"
    app = json.loads(run(["yq", "-o=json", ".", str(path)], capture_output=True).stdout)
    if app["spec"]["destination"]["name"] != cluster or app["metadata"]["name"] != f"k8up-{suffix}":
        raise RuntimeError("Unexpected Application destination or name")
    for source in app["spec"]["sources"]:
        if source["repoURL"] == REPO:
            source["targetRevision"] = revision
    run(HUB + ["apply", "--server-side", "-f", "-"], input=json.dumps(app))
    name = app["metadata"]["name"]
    run(HUB + ["-n", "argo-system", "annotate", "application", name, "argocd.argoproj.io/refresh=hard", "--overwrite"])
    run(HUB + ["-n", "argo-system", "wait", "--for=jsonpath={.status.sync.status}=Synced", f"application/{name}", "--timeout=300s"])
    verify(cluster, False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "status", "verify"])
    parser.add_argument("cluster", choices=TARGETS)
    parser.add_argument("--revision", default="main", help="Repository revision for explicit pre-merge Argo bootstrap")
    parser.add_argument("--expect-idle", action="store_true", help="Require no K8up schedules or backup/restore/prune resources")
    args = parser.parse_args()
    try:
        if args.action == "bootstrap":
            bootstrap(args.cluster, args.revision)
        elif args.action == "verify":
            verify(args.cluster, args.expect_idle)
        else:
            suffix, kubeconfig = TARGETS[args.cluster]
            run(HUB + ["-n", "argo-system", "get", "application", f"k8up-{suffix}"])
            run(["kubectl", "--kubeconfig", str(kubeconfig), "-n", "backups", "get", "deployment,pods", "-l", "app.kubernetes.io/instance=k8up"])
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
