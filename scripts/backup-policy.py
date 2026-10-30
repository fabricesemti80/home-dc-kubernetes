#!/usr/bin/env python3
"""Exercise the actual GitOps policy templates without installing schedules."""

import argparse
import copy
import json
import subprocess
import sys

from backup_apps import ROOT, SOURCES, Resources, doppler
from k8up_pilot import TARGETS


def render(cluster):
    result = subprocess.run(
        [
            "kubectl",
            "kustomize",
            str(ROOT / f"kubernetes/apps/{cluster}/storage/k8up/config"),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    # kubectl supplies Kubernetes' YAML parser; no workstation PyYAML dependency.
    parsed = subprocess.run(
        [
            "kubectl",
            "--kubeconfig",
            str(TARGETS[cluster][0]),
            "create",
            "--dry-run=client",
            "--validate=false",
            "-f",
            "-",
            "-o",
            "json",
        ],
        input=result.stdout,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    decoder, objects, offset = json.JSONDecoder(), [], 0
    while offset < len(parsed.stdout):
        if parsed.stdout[offset].isspace():
            offset += 1
            continue
        value, offset = decoder.raw_decode(parsed.stdout, offset)
        objects.extend(value.get("items", [value]))
    return objects


def alerts_bootstrap():
    expected = doppler("apps", "SLACK_WEBHOOK_MONITORING")
    names = subprocess.run(
        [
            "doppler",
            "secrets",
            "--project",
            "home-dc-kubernetes",
            "--config",
            "infra",
            "--only-names",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if "SLACK_WEBHOOK_MONITORING" in json.loads(names.stdout):
        if doppler("infra", "SLACK_WEBHOOK_MONITORING") != expected:
            raise RuntimeError(
                "Existing infra alert route differs; refusing to overwrite"
            )
    else:
        result = subprocess.run(
            [
                "doppler",
                "secrets",
                "set",
                "SLACK_WEBHOOK_MONITORING",
                "--project",
                "home-dc-kubernetes",
                "--config",
                "infra",
                "--visibility",
                "masked",
                "--json",
                "--silent",
            ],
            input=expected,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if result.returncode:
            raise RuntimeError(
                "Cannot provision infra alert route; credential output suppressed"
            )
    print(
        "Both cluster configurations have the existing monitoring Slack route; no credential rotated"
    )


def verify(cluster):
    items = render(cluster)
    result = subprocess.run(
        [
            "kubectl",
            "--kubeconfig",
            str(TARGETS[cluster][0]),
            "apply",
            "--server-side",
            "--dry-run=server",
            "--field-manager=backup-policy-validation",
            "--force-conflicts",
            "-f",
            "-",
        ],
        input=json.dumps({"apiVersion": "v1", "kind": "List", "items": items}),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        # Rendered policy contains references only, never Secret values.
        sys.stderr.write(result.stderr)
        raise RuntimeError("Server rejected the rendered GitOps backup policy")
    print(
        json.dumps(
            {"cluster": cluster, "server_dry_run_passed": True, "resources": len(items)}
        )
    )


def run(cluster, action):
    source = next(s for s in SOURCES.values() if s["cluster"] == cluster)
    namespace = source["namespace"]
    documents = render(cluster)
    resources = Resources(cluster, namespace)
    try:
        if action != "check-data":
            config = next(
                copy.deepcopy(i)
                for i in documents
                if i["kind"] == "ConfigMap"
                and i["metadata"]["name"] == "backup-runtime"
            )
            config["metadata"] = {"name": resources.name}
            resources.create(config)
        config_name = "apps" if cluster == "app-cluster" else "infra"
        repo_key = f"K8UP_{namespace}_CRITICAL_6H_PASSWORD".upper()
        credentials = {repo_key: doppler(config_name, repo_key)}
        if action != "check-data":
            credentials["SLACK_WEBHOOK_MONITORING"] = doppler(
                config_name, "SLACK_WEBHOOK_MONITORING"
            )
        resources.create(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": resources.name},
                "stringData": credentials,
            }
        )
        sa = "k8up-policy-auditor"
        if action != "check-data":
            for kind in ["ServiceAccount", "Role", "RoleBinding"]:
                obj = next(
                    copy.deepcopy(i)
                    for i in documents
                    if i["kind"] == kind and i["metadata"]["name"] == sa
                )
                obj["metadata"] = {"name": resources.name}
                if kind == "RoleBinding":
                    obj["roleRef"]["name"] = resources.name
                    obj["subjects"][0]["name"] = resources.name
                resources.create(obj)
        cron_name = (
            "critical-6h-read-data" if action == "check-data" else "critical-6h-audit"
        )
        template = next(
            copy.deepcopy(i["spec"]["jobTemplate"])
            for i in documents
            if i["kind"] == "CronJob" and i["metadata"]["name"] == cron_name
        )
        pod = template["spec"]["template"]["spec"]
        if "serviceAccountName" in pod:
            pod["serviceAccountName"] = resources.name
        for volume in pod["volumes"]:
            if volume["name"] == "repository":
                volume.pop("persistentVolumeClaim")
                volume["nfs"] = {"server": "10.0.40.2", "path": "/k8s-backup"}
            if (
                "configMap" in volume
                and volume["configMap"]["name"] == "backup-runtime"
            ):
                volume["configMap"]["name"] = resources.name
        for container in pod["containers"]:
            for environment in container.get("env", []):
                reference = environment.get("valueFrom", {}).get("secretKeyRef")
                if reference and reference["name"] == "k8up-source-credentials":
                    reference["name"] = resources.name
            if action != "check-data":
                container["env"].extend(
                    [
                        {"name": "NOTIFY_ALWAYS", "value": "true"},
                        {
                            "name": "AUDIT_STATE_PATH",
                            "value": f"/repository/{cluster}/{namespace}/.{resources.name}-audit.json",
                        },
                    ]
                )
        if action == "smoke":
            # Real missing-source alert, then real recovery, using the same state.
            negative = copy.deepcopy(config)
            inventory = json.loads(negative["data"]["sources.json"])
            inventory["coverage-negative-probe"] = source
            negative["data"]["sources.json"] = json.dumps(inventory)
            resources.call(
                "patch",
                "configmap",
                resources.name,
                "--type=merge",
                "-p",
                json.dumps({"data": negative["data"]}),
            )

        def execute(suffix, expected_success):
            job = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": resources.name + suffix,
                    "labels": template.get("metadata", {}).get("labels", {}),
                },
                "spec": copy.deepcopy(template["spec"]),
            }
            if action != "check-data" and expected_success:
                job["spec"]["template"]["spec"]["containers"][0]["command"] = [
                    "sh",
                    "-ec",
                    'python3 /scripts/audit.py; rm -f "$AUDIT_STATE_PATH"',
                ]
            if action == "check-data":
                job["spec"]["ttlSecondsAfterFinished"] = 36 * 86400
            resources.create(job, retain=action == "check-data")
            condition = "Complete" if expected_success else "Failed"
            wait = resources.call(
                "wait",
                "--for=condition=" + condition,
                "job/" + job["metadata"]["name"],
                "--timeout=900s" if action == "check-data" else "--timeout=300s",
                check=False,
            )
            result = resources.get("job", job["metadata"]["name"])
            success = bool(result.get("status", {}).get("succeeded"))
            output = resources.call(
                "logs", "job/" + job["metadata"]["name"], check=False
            ).stdout
            print(output, end="", flush=True)
            if wait.returncode or success != expected_success:
                raise RuntimeError(
                    "Policy-template Job did not reach the expected terminal result"
                )

        if action == "smoke":
            execute("-missing", False)
            resources.call(
                "patch",
                "configmap",
                resources.name,
                "--type=merge",
                "-p",
                json.dumps({"data": config["data"]}),
            )
            execute("-recovered", True)
        else:
            execute("-run", True)
    finally:
        resources.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["verify", "audit", "smoke", "check-data", "alerts-bootstrap"]
    )
    parser.add_argument("cluster", nargs="?", choices=TARGETS)
    args = parser.parse_args()
    try:
        if args.action == "alerts-bootstrap":
            alerts_bootstrap()
        elif not args.cluster:
            parser.error("An explicit cluster is required")
        elif args.action == "verify":
            verify(args.cluster)
        else:
            run(args.cluster, args.action)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
