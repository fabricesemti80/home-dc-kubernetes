"""Publish a validated copy of an app's config volume for Backrest.

snapshot (root, source mounted read-only): copy source -> /stage, excluding
disposable paths; every SQLite database copy must pass integrity_check, else
retry. Fails closed: the previously published copy is never touched on error.
publish (NAS writer UID): atomically swap /stage into <exports>/<app>/current.
"""

import fnmatch
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

app = os.environ["BACKUP_APP"]
stage = Path("/stage/data")
dest_root = Path("/backups") / os.environ["CLUSTER_NAME"] / "exports" / app
excludes = json.loads(os.environ.get("BACKUP_EXCLUDES", "[]"))


def ignore(directory, names):
    rel = Path(directory).relative_to("/source")
    skipped = []
    for name in names:
        path = str(rel / name)
        if any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in excludes):
            skipped.append(name)
    return skipped


def sqlite_files(root):
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as handle:
                if handle.read(16) == b"SQLite format 3\x00":
                    yield path


def snapshot():
    last = None
    for attempt in range(1, 4):
        shutil.rmtree(stage, ignore_errors=True)
        shutil.copytree("/source", stage, symlinks=True, ignore=ignore, dirs_exist_ok=False)
        try:
            databases = list(sqlite_files(stage))
            for db in databases:
                # Replays the copied WAL into the copy; result is self-contained.
                con = sqlite3.connect(db)
                try:
                    result = con.execute("PRAGMA integrity_check").fetchall()
                    if result != [("ok",)]:
                        raise RuntimeError(f"{db.relative_to(stage)}: {result[:3]}")
                    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    con.close()
            break
        except Exception as exc:  # noqa: BLE001 - retry on any inconsistent copy
            last = exc
            print(f"attempt {attempt}: inconsistent copy: {exc}", file=sys.stderr)
            time.sleep(5)
    else:
        raise SystemExit(f"no consistent copy after 3 attempts: {last}")
    if not any(stage.iterdir()):
        raise SystemExit("source produced an empty copy")
    for path in [stage, *stage.rglob("*")]:
        os.lchown(path, 1004, 65534)
    print(f"snapshot ok: {len(databases)} SQLite database(s) verified")


def publish():
    os.umask(0o077)
    app_dir = dest_root
    app_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    new, old, current = app_dir / ".new", app_dir / ".old", app_dir / "current"
    if old.exists() and not current.exists():
        old.rename(current)
    for leftover in (new, old):
        shutil.rmtree(leftover, ignore_errors=True)
    shutil.copytree(stage, new, symlinks=True)
    (new / ".captured-at").write_text(datetime.now(timezone.utc).isoformat() + "\n")
    if current.exists():
        current.rename(old)
    new.rename(current)
    shutil.rmtree(old, ignore_errors=True)
    print("published; contents suppressed")


{"snapshot": snapshot, "publish": publish}[sys.argv[1]]()
