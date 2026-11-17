#!/usr/bin/env python3
"""Manage the public and internal DNS zones declared in domains.yaml.

Argo CD has no variable substitution, so manifests keep literal hostnames and
this tool keeps them consistent with domains.yaml:

  domains.py check                      validate every HTTPRoute against domains.yaml
  domains.py env                        print DOMAIN_* shell assignments
  domains.py rename KIND FROM TO        dry-run a zone rename (lists files)
  domains.py rename KIND FROM TO --write [--force]
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "domains.yaml"
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
KINDS = ("public", "internal")
# Gateway -> zone kind its hostnames must belong to.
GATEWAY_KIND = {"envoy-external": "public", "envoy-internal": "internal"}
SENTINEL = "\x00PRESERVE{}\x00"


def load_config(path: Path = CONFIG) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for kind in KINDS:
        zones = data.get(kind)
        if not isinstance(zones, list) or not zones or not all(isinstance(z, str) for z in zones):
            raise SystemExit(f"{path.name}: '{kind}' must be a non-empty list of zones")
        data[kind] = [z.strip().lower().rstrip(".") for z in zones]
    overlap = set(data["public"]) & set(data["internal"])
    if overlap:
        raise SystemExit(f"{path.name}: zones listed as both public and internal: {sorted(overlap)}")
    data.setdefault("preserve", [])
    data.setdefault("rename_exclude", [])
    return data


def public_zones() -> list[str]:
    return load_config()["public"]


def internal_zones() -> list[str]:
    return load_config()["internal"]


def zone_of(host: str, zones: list[str]) -> str | None:
    """Return the zone `host` belongs to, longest match first."""
    host = host.lower().rstrip(".")
    for zone in sorted(zones, key=len, reverse=True):
        if host == zone or host.endswith("." + zone):
            return zone
    return None


def is_public_host(host: str) -> bool:
    return zone_of(host, public_zones()) is not None


def strip_zone(host: str, zones: list[str]) -> str:
    zone = zone_of(host, zones)
    return host[: -(len(zone) + 1)] if zone and host != zone else host


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p]


# ---------------------------------------------------------------- check


def iter_routes():
    for path in sorted((ROOT / "kubernetes").rglob("*.y*ml")):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError:
            continue
        for doc in docs:
            if isinstance(doc, dict) and doc.get("kind") == "HTTPRoute":
                yield path, doc


def check(cfg: dict) -> int:
    all_zones = cfg["public"] + cfg["internal"]
    errors: list[str] = []
    routes = 0
    for path, doc in iter_routes():
        routes += 1
        rel = path.relative_to(ROOT)
        name = doc.get("metadata", {}).get("name", "?")
        hosts = [str(h) for h in doc.get("spec", {}).get("hostnames") or []]
        annotations = doc.get("metadata", {}).get("annotations") or {}
        dns_host = annotations.get("external-dns.alpha.kubernetes.io/hostname")
        if dns_host:
            hosts += [h.strip() for h in str(dns_host).split(",")]
        kinds = {
            GATEWAY_KIND[ref.get("name")]
            for ref in doc.get("spec", {}).get("parentRefs") or []
            if ref.get("name") in GATEWAY_KIND
        }
        for host in hosts:
            if zone_of(host, all_zones) is None:
                errors.append(f"{rel} ({name}): {host} is not under a zone in domains.yaml")
                continue
            # A route on a single gateway must use that gateway's zone kind.
            if len(kinds) == 1:
                kind = next(iter(kinds))
                if zone_of(host, cfg[kind]) is None:
                    errors.append(f"{rel} ({name}): {host} is on a {kind} gateway but not in a {kind} zone")
    for err in errors:
        print(f"error: {err}", file=sys.stderr)
    if errors:
        return 1
    print(f"domains: {routes} HTTPRoutes match public={cfg['public']} internal={cfg['internal']}")
    return 0


# ---------------------------------------------------------------- rename


def domain_pattern(domain: str) -> re.Pattern:
    # Match the zone and any subdomain of it, but not a longer label
    # (example.dev must not match example.devices or my-example.dev).
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(domain) + r"(?![A-Za-z0-9-])", re.IGNORECASE)


def rename_text(text: str, pattern: re.Pattern, new: str, preserve: list[str]) -> tuple[str, int]:
    masked = text
    for i, keep in enumerate(preserve):
        masked = masked.replace(keep, SENTINEL.format(i))
    masked, count = pattern.subn(new, masked)
    for i, keep in enumerate(preserve):
        masked = masked.replace(SENTINEL.format(i), keep)
    return masked, count


def excluded(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def rename(cfg: dict, kind: str, old: str, new: str, write: bool, force: bool = False) -> int:
    old, new = old.lower().rstrip("."), new.lower().rstrip(".")
    if old not in cfg[kind]:
        raise SystemExit(f"{old} is not a {kind} zone in domains.yaml ({cfg[kind]})")
    if new in cfg["public"] + cfg["internal"]:
        raise SystemExit(f"{new} is already listed in domains.yaml")
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", new):
        raise SystemExit(f"{new} is not a valid DNS zone")
    # A zone nested in another (home -> lab.home) would be matched twice.
    for other in cfg["public"] + cfg["internal"]:
        if other != old and (other.endswith("." + new) or new.endswith("." + other)):
            raise SystemExit(f"{new} overlaps existing zone {other}; rename it in two steps")

    pattern = domain_pattern(old)
    files = [
        p for p in tracked_files()
        if p.is_file()
        and p.relative_to(ROOT).as_posix() != SELF
        and not excluded(p.relative_to(ROOT).as_posix(), cfg["rename_exclude"])
    ]
    # If the new zone already appears, a later rename back would also rewrite
    # those unrelated mentions, so the change could not be reverted cleanly.
    clash = domain_pattern(new)
    collisions = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
            for keep in cfg["preserve"]:
                text = text.replace(keep, "")
            if clash.search(text):
                collisions.append(path.relative_to(ROOT).as_posix())
        except (UnicodeDecodeError, OSError):
            continue
    if collisions and not force:
        print(f"{new} already appears in: {', '.join(collisions)}", file=sys.stderr)
        raise SystemExit("Refusing: the rename would not be reversible. Edit those files or pass --force.")

    changed: list[tuple[str, int]] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text, count = rename_text(text, pattern, new, cfg["preserve"])
        if count:
            changed.append((rel, count))
            if write:
                path.write_text(new_text, encoding="utf-8")

    total = sum(c for _, c in changed)
    for rel, count in changed:
        print(f"{count:4d}  {rel}")
    verb = "Renamed" if write else "Would rename"
    print(f"{verb} {total} occurrences of {old} -> {new} in {len(changed)} files.")
    if not write:
        print("Dry run: re-run with --write to apply.")
        return 0

    print("\nOut-of-repo steps still needed (see docs/cluster/domains.md#changing-a-domain).")
    cfg_new = load_config()
    return check(cfg_new)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate HTTPRoute hostnames against domains.yaml")
    sub.add_parser("env", help="print DOMAIN_* shell assignments")
    p = sub.add_parser("rename", help="rename a zone across the repository")
    p.add_argument("kind", choices=KINDS)
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--write", action="store_true", help="apply changes (default: dry run)")
    p.add_argument("--force", action="store_true", help="rename even if the new zone already appears")
    args = parser.parse_args()

    cfg = load_config()
    if args.cmd == "check":
        return check(cfg)
    if args.cmd == "env":
        print(f"DOMAIN_PUBLIC={cfg['public'][0]}")
        print(f"DOMAIN_INTERNAL={cfg['internal'][0]}")
        print(f"DOMAINS_PUBLIC={','.join(cfg['public'])}")
        print(f"DOMAINS_INTERNAL={','.join(cfg['internal'])}")
        return 0
    return rename(cfg, args.kind, args.old, args.new, args.write, args.force)


if __name__ == "__main__":
    sys.exit(main())
