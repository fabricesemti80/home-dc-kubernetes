#!/usr/bin/env python3
"""Ensure HTTPRoutes have homepage annotations and keep the homepage layout in sync."""
import glob
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS_DIR = os.path.join(REPO, "kubernetes", "apps")
SETTINGS_PATH = os.path.join(
    REPO, "kubernetes", "apps", "app-cluster", "web", "homepage", "config", "settings.yaml"
)
SERVICES_PATH = os.path.join(
    REPO, "kubernetes", "apps", "app-cluster", "web", "homepage", "config", "services.yaml"
)

CLUSTER_LABELS = {
    "app-cluster": "App Cluster",
    "infra-cluster": "Infra Cluster",
}

ICON_MAP = {
    "argo-cd": "argo-cd.png",
    "alertmanager": "alertmanager.png",
    "code-server": "vscode.png",
    "glance": "glance.png",
    "grafana": "grafana.png",
    "homepage": "homepage.png",
    "immich": "immich.png",
    "jellyfin": "jellyfin.png",
    "jellyseerr": "jellyseerr.png",
    "kestra": "mdi-rocket-launch",
    "linkwarden": "linkwarden.png",
    "prowlarr": "prowlarr.png",
    "prometheus": "prometheus.png",
    "pulse": "mdi-heart-pulse",
    "qbittorrent": "qbittorrent.png",
    "radarr": "radarr.png",
    "sabnzbd": "sabnzbd.png",
    "sonarr": "sonarr.png",
    "sterling-pdf": "stirling-pdf.png",
    "tdarr": "tdarr.png",
    "uptime-kuma": "mdi-monitor-eye",
}

DESCRIPTIONS = {
    "argo-cd": "GitOps control plane",
    "alertmanager": "Alert routing and silences",
    "code-server": "Browser IDE with cluster tooling",
    "glance": "Lightweight landing page",
    "grafana": "Dashboards and metrics exploration",
    "homepage": "Kubernetes-native homelab dashboard",
    "immich": "Photo and video management",
    "jellyfin": "Media streaming server",
    "jellyseerr": "Media requests and approvals",
    "kestra": "Infra automation and orchestration",
    "linkwarden": "Bookmark and knowledge archive",
    "prowlarr": "Indexer aggregation",
    "prometheus": "PromQL queries and time-series exploration",
    "pulse": "Infrastructure monitoring",
    "qbittorrent": "BitTorrent client",
    "radarr": "Movie library automation",
    "sabnzbd": "Usenet downloader",
    "sonarr": "Series library automation",
    "sterling-pdf": "PDF editor and manipulation tool",
    "tdarr": "Distributed media transcoding and health checks",
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


def upgrade_http_to_https(href: str) -> str:
    """Upgrade http:// to https:// for public .dev hosts, preserving path/query."""
    if not href.startswith("http://"):
        return href
    host = href.split("/")[2].split(":")[0]
    if not host.endswith(".dev"):
        return href
    parts = urlsplit(href)
    return urlunsplit(parts._replace(scheme="https"))


def route_host(doc: dict) -> str | None:
    annotations = doc.get("metadata", {}).get("annotations", {})
    host = annotations.get("external-dns.alpha.kubernetes.io/hostname")
    if not host:
        hostnames = doc.get("spec", {}).get("hostnames", [])
        if hostnames:
            host = hostnames[0]
    return host


def is_public_route(doc: dict) -> bool:
    """Only public DNS records (currently .dev) should appear on the homepage."""
    host = route_host(doc)
    return bool(host and host.endswith(".dev"))


def determine_href(doc: dict) -> str | None:
    host = route_host(doc)
    if not host:
        return None
    # Public .dev endpoints terminate TLS at Cloudflare, so use HTTPS.
    scheme = "https" if host.endswith(".dev") else "http"
    return f"{scheme}://{host}"


def desired_annotations(doc: dict, cluster_key: str, namespace: str, app: str) -> dict | None:
    if not is_public_route(doc):
        return None

    route_name = doc.get("metadata", {}).get("name", app)
    display_name = title_name(route_name)

    group = f"{CLUSTER_LABELS.get(cluster_key, cluster_key)} - {namespace}"
    icon = ICON_MAP.get(route_name.lower(), "mdi-application")
    description = DESCRIPTIONS.get(
        route_name.lower(), f"{title_name(route_name)} service"
    )
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
    """Insert, update, or remove homepage annotations while preserving file style."""
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

        if not desired:
            # Dropping all homepage annotations. If nothing else is left, remove the
            # empty annotations: key as well.
            rest = [line for line in kept if line.strip() and not line.strip().startswith("#")]
            if not rest:
                new_lines = new_lines[:ann_start] + new_lines[ann_end:]
                return new_lines, new_lines != lines
            new_block = [new_lines[ann_start]] + kept
            new_lines = new_lines[:ann_start] + new_block + new_lines[ann_end:]
            return new_lines, new_lines != lines

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
        return new_lines, new_lines != lines

    if not desired:
        return new_lines, False

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


def update_route_file(path: str, changed: set, groups: set) -> dict | None:
    """Update annotations in an HTTPRoute file and return its homepage metadata."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    docs = list(yaml.safe_load_all(text))
    desired = None
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

        if desired is None:
            # Internal route: strip any existing homepage annotations.
            if existing_homepage:
                desired = {}
            continue

        for k, v in existing_homepage.items():
            if k == "gethomepage.dev/group":
                continue
            if k == "gethomepage.dev/href":
                desired[k] = upgrade_http_to_https(v)
                continue
            desired[k] = v

        groups.add(desired["gethomepage.dev/group"])

    # desired is None and no existing homepage annotations -> nothing to do
    if desired is None:
        return None

    lines = text.splitlines(keepends=True)
    new_lines, modified = update_annotations_block(lines, desired)
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        changed.add(os.path.relpath(path, REPO))

    return desired if desired else None


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


def update_services(infra_routes: list[dict]) -> bool:
    """Write static services.yaml entries for infra-cluster routes.

    The app-cluster homepage runs in cluster discovery mode and can only see
    app-cluster HTTPRoutes. Infra-cluster routes are supplied statically here
    so they still appear on the dashboard.
    """
    if not infra_routes:
        text = "[]\n"
    else:
        # Sort by group, then weight, then name for stable output.
        sorted_routes = sorted(
            infra_routes,
            key=lambda r: (
                r["gethomepage.dev/group"],
                int(r.get("gethomepage.dev/weight", "0")),
                r["gethomepage.dev/name"],
            ),
        )
        lines = []
        current_group = None
        for route in sorted_routes:
            group = route["gethomepage.dev/group"]
            name = route["gethomepage.dev/name"]
            icon = route["gethomepage.dev/icon"]
            href = route.get("gethomepage.dev/href", "")
            description = route["gethomepage.dev/description"]

            if group != current_group:
                if current_group is not None:
                    lines.append("")
                lines.append(f"- {group}:")
                current_group = group

            lines.append(f"    - {name}:")
            lines.append(f"        icon: {icon}")
            if href:
                lines.append(f"        href: {href}")
            lines.append(f"        description: {description}")

        text = "\n".join(lines) + "\n"

    existing = ""
    if os.path.exists(SERVICES_PATH):
        with open(SERVICES_PATH, "r", encoding="utf-8") as f:
            existing = f.read()

    if text != existing:
        with open(SERVICES_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    return False


def main():
    changed = set()
    groups = set()
    infra_routes: list[dict] = []

    route_files = sorted(
        glob.glob(os.path.join(APPS_DIR, "**", "*http-route*.yaml"), recursive=True)
        + glob.glob(os.path.join(APPS_DIR, "**", "httproute*.yaml"), recursive=True)
    )

    for path in route_files:
        if should_skip(path):
            continue
        route = update_route_file(path, changed, groups)
        if route is None:
            continue
        cluster_key, _, _ = parse_app_path(path)
        if cluster_key == "infra-cluster":
            infra_routes.append(route)

    settings_changed = update_settings(groups)
    if settings_changed:
        changed.add(os.path.relpath(SETTINGS_PATH, REPO))

    services_changed = update_services(infra_routes)
    if services_changed:
        changed.add(os.path.relpath(SERVICES_PATH, REPO))

    if changed:
        print("Updated files:")
        for f in sorted(changed):
            print(f"  {f}")
    else:
        print("All HTTPRoutes already have the expected homepage annotations.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
