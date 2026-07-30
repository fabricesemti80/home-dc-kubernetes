#!/usr/bin/env python3
"""Ensure HTTPRoutes have homepage annotations and keep the homepage layout in sync."""
import glob
import os
import re
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_DIR = os.path.join(REPO, "kubernetes", "apps")
SETTINGS_PATH = os.path.join(
    REPO, "kubernetes", "apps", "app-cluster", "web", "homepage", "config", "settings.yaml"
)

CLUSTER_LABELS = {
    "app-cluster": "App Cluster",
    "infra-cluster": "Infra Cluster",
}

ICON_MAP = {
    "argo-cd": "argo-cd.png",
    "alertmanager": "alertmanager.png",
    "code-server": "vscode.png",
    "convertx": "mdi-file-convert",
    "glance": "glance.png",
    "grafana": "grafana.png",
    "homepage": "homepage.png",
    "immich": "immich.png",
    "jellyfin": "jellyfin.png",
    "jellyseerr": "jellyseerr.png",
    "kestra": "mdi-rocket-launch",
    "linkwarden": "linkwarden.png",
    "n8n": "n8n.png",
    "prowlarr": "prowlarr.png",
    "prometheus": "prometheus.png",
    "pulse": "mdi-heart-pulse",
    "qbittorrent": "qbittorrent.png",
    "radarr": "radarr.png",
    "sabnzbd": "sabnzbd.png",
    "sonarr": "sonarr.png",
    "sterling-pdf": "stirling-pdf.png",
    "tdarr": "tdarr.png",
    "termix": "terminal.png",
    "uptime-kuma": "mdi-monitor-eye",
}

DESCRIPTIONS = {
    "argo-cd": "GitOps control plane",
    "alertmanager": "Alert routing and silences",
    "code-server": "Browser IDE with cluster tooling",
    "convertx": "File converter",
    "glance": "Lightweight landing page",
    "grafana": "Dashboards and metrics exploration",
    "homepage": "Kubernetes-native homelab dashboard",
    "immich": "Photo and video management",
    "jellyfin": "Media streaming server",
    "jellyseerr": "Media requests and approvals",
    "kestra": "Infra automation and orchestration",
    "linkwarden": "Bookmark and knowledge archive",
    "n8n": "Workflow automation platform",
    "prowlarr": "Indexer aggregation",
    "prometheus": "PromQL queries and time-series exploration",
    "pulse": "Infrastructure monitoring",
    "qbittorrent": "BitTorrent client",
    "radarr": "Movie library automation",
    "sabnzbd": "Usenet downloader",
    "sonarr": "Series library automation",
    "sterling-pdf": "PDF editor and manipulation tool",
    "tdarr": "Distributed media transcoding and health checks",
    "termix": "Internal SSH and server access",
    "uptime-kuma": "External availability monitoring",
}

SKIP_PATTERNS = [
    ".sops.",
    "nginx-test",
]


def should_skip(path: str) -> bool:
    rel = os.path.relpath(path, REPO)
    return any(p in rel for p in SKIP_PATTERNS)


def parse_app_path(path: str):
    """Return (cluster_key, namespace, app) from a kubernetes/apps path."""
    rel = os.path.relpath(path, APPS_DIR)
    parts = rel.split(os.sep)
    cluster_key = parts[0]
    namespace = parts[1] if len(parts) > 1 else "default"
    app = parts[2] if len(parts) > 2 else namespace
    return cluster_key, namespace, app


def title_name(name: str) -> str:
    base = name.replace("-", " ").replace("_", " ")
    return " ".join(w.capitalize() for w in base.split())


def determine_href(doc: dict) -> str | None:
    annotations = doc.get("metadata", {}).get("annotations", {})
    host = annotations.get("external-dns.alpha.kubernetes.io/hostname")
    if not host:
        hostnames = doc.get("spec", {}).get("hostnames", [])
        if hostnames:
            host = hostnames[0]
    if not host:
        return None

    scheme = "https"
    for parent in doc.get("spec", {}).get("parentRefs", []):
        if parent.get("sectionName") == "http":
            scheme = "http"
            break
    return f"{scheme}://{host}"


def desired_annotations(doc: dict, cluster_key: str, namespace: str, app: str) -> dict:
    route_name = doc.get("metadata", {}).get("name", app)
    is_internal = route_name.endswith("-internal")
    display_base = route_name.removesuffix("-internal")
    display_name = title_name(display_base)
    if is_internal:
        display_name = f"{display_name} (internal)"

    group = f"{CLUSTER_LABELS.get(cluster_key, cluster_key)} - {namespace}"
    icon = ICON_MAP.get(display_base.lower(), "mdi-application")
    description = DESCRIPTIONS.get(
        display_base.lower(), f"{title_name(display_base)} service"
    )
    if is_internal:
        description = f"{description} (internal)"

    weight = "10" if cluster_key == "app-cluster" else "20"

    desired = {
        "gethomepage.dev/enabled": "true",
        "gethomepage.dev/group": group,
        "gethomepage.dev/name": display_name,
        "gethomepage.dev/icon": icon,
        "gethomepage.dev/description": description,
        "gethomepage.dev/weight": weight,
    }
    href = determine_href(doc)
    if href:
        desired["gethomepage.dev/href"] = href
    return desired


def get_line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def update_annotations_block(lines: list[str], desired: dict) -> tuple[list[str], bool]:
    """Insert or update homepage annotations while preserving file style."""
    new_lines = list(lines)

    # Find metadata: line
    try:
        metadata_idx = next(
            i for i, line in enumerate(new_lines) if line.strip() == "metadata:"
        )
    except StopIteration:
        return new_lines, False

    # Find existing annotations: block within metadata
    ann_start = None
    ann_indent = None
    for i in range(metadata_idx + 1, len(new_lines)):
        line = new_lines[i]
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = get_line_indent(line)
        if indent <= get_line_indent(new_lines[metadata_idx]):
            break
        if line.strip() == "annotations:":
            ann_start = i
            ann_indent = indent
            break

    if ann_start is not None:
        # Find end of annotations block
        ann_end = ann_start + 1
        for i in range(ann_start + 1, len(new_lines)):
            line = new_lines[i]
            if not line.strip() or line.strip().startswith("#"):
                ann_end = i + 1
                continue
            if get_line_indent(line) <= ann_indent:
                break
            ann_end = i + 1

        # Remove existing gethomepage.dev lines
        kept = []
        modified = False
        for i in range(ann_start + 1, ann_end):
            line = new_lines[i]
            stripped = line.strip()
            if stripped.startswith("gethomepage.dev/"):
                modified = True
                continue
            kept.append(line)

        # Build new homepage annotation lines
        key_indent = " " * (ann_indent + 2)
        homepage_lines = [
            f'{key_indent}{key}: "{value}"\n' for key, value in sorted(desired.items())
        ]

        # Preserve any blank lines/comments at the top of the block
        prefix = []
        for line in kept:
            if not line.strip() or line.strip().startswith("#"):
                prefix.append(line)
            else:
                break
        rest = kept[len(prefix) :]

        new_block = (
            [new_lines[ann_start]]
            + prefix
            + rest
            + homepage_lines
        )
        new_lines = new_lines[: ann_start] + new_block + new_lines[ann_end:]
        return new_lines, True

    # No annotations block: insert one at the end of the metadata block
    base_indent = get_line_indent(new_lines[metadata_idx])
    ann_key_indent = " " * (base_indent + 2)
    val_indent = " " * (base_indent + 4)
    homepage_lines = [
        f"{ann_key_indent}annotations:\n",
    ] + [
        f'{val_indent}{key}: "{value}"\n' for key, value in sorted(desired.items())
    ]

    # Find the end of the metadata block (next top-level key)
    insert_idx = metadata_idx + 1
    while insert_idx < len(new_lines):
        line = new_lines[insert_idx]
        if not line.strip() or line.strip().startswith("#"):
            insert_idx += 1
            continue
        if get_line_indent(line) <= base_indent:
            break
        insert_idx += 1

    new_lines = (
        new_lines[:insert_idx]
        + homepage_lines
        + new_lines[insert_idx:]
    )
    return new_lines, True


def update_route_file(path: str, changed: set, groups: set) -> None:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    docs = list(yaml.safe_load_all(text))
    for doc in docs:
        if not doc or doc.get("kind") != "HTTPRoute":
            continue
        cluster_key, namespace, app = parse_app_path(path)
        desired = desired_annotations(doc, cluster_key, namespace, app)

        # Preserve manually-set homepage values (name, icon, description, weight, href, app, widgets)
        # but always normalize the group to the cluster/namespace scheme.
        existing_homepage = {
            k: str(v)
            for k, v in doc.get("metadata", {}).get("annotations", {}).items()
            if k.startswith("gethomepage.dev/")
        }
        for k, v in existing_homepage.items():
            if k == "gethomepage.dev/group":
                continue
            desired[k] = v

        groups.add(desired["gethomepage.dev/group"])

    lines = text.splitlines(keepends=True)
    new_lines, modified = update_annotations_block(lines, desired)
    if not modified:
        return

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    changed.add(os.path.relpath(path, REPO))


def update_settings(groups: set) -> bool:
    if not os.path.exists(SETTINGS_PATH):
        return False
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    sorted_groups = sorted(groups)
    layout_block = "layout:\n" + "".join(f"  {g}:\n" for g in sorted_groups)

    if "layout:" in text:
        new_text = re.sub(r"layout:\n(?:  .*:\n)*", layout_block, text)
    else:
        new_text = text.rstrip() + "\n\n" + layout_block

    if new_text != text:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write(new_text)
        return True
    return False


def main():
    changed = set()
    groups = set()

    route_files = sorted(
        glob.glob(os.path.join(APPS_DIR, "**", "*http-route*.yaml"), recursive=True)
        + glob.glob(os.path.join(APPS_DIR, "**", "httproute*.yaml"), recursive=True)
    )

    for path in route_files:
        if should_skip(path):
            continue
        update_route_file(path, changed, groups)

    settings_changed = update_settings(groups)
    if settings_changed:
        changed.add(os.path.relpath(SETTINGS_PATH, REPO))

    if changed:
        print("Updated files:")
        for f in sorted(changed):
            print(f"  {f}")
    else:
        print("All HTTPRoutes already have the expected homepage annotations.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
