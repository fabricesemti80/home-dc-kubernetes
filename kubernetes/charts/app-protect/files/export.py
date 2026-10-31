"""Publish a validated copy of an app's config volume for Backrest.

snapshot (root): copy source -> /stage, excluding disposable paths. SQLite
databases are never file-copied: each is read through SQLite's online backup API
(one read transaction, so a transactionally consistent state even while the app
writes) and the result must pass integrity_check. The source volume is mounted
read-write only so SQLite can take WAL read locks; connections are mode=ro.
Fails closed: the previously published copy is never touched on error.
publish (NAS writer UID): atomically swap /stage into <exports>/<app>/current.
"""

import fnmatch
import json
import os
import shutil
import sqlite3
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

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


def is_sqlite(path):
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


databases = []


def copy_file(src, dst):
    src = Path(src)
    if is_sqlite(src):
        source = sqlite3.connect(f"file:{quote(str(src))}?mode=ro", uri=True, timeout=30)
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
            result = target.execute("PRAGMA integrity_check").fetchall()
            if result != [("ok",)]:
                raise RuntimeError(f"{src}: integrity_check {result[:3]}")
            target.execute("PRAGMA journal_mode=DELETE")
        finally:
            target.close()
            source.close()
        databases.append(src)
    elif src.name.endswith(("-wal", "-shm", "-journal")) and is_sqlite(
        src.with_name(src.name.rsplit("-", 1)[0])
    ):
        return  # live companion of a database captured through the backup API
    elif stat.S_ISREG(src.lstat().st_mode):
        shutil.copy2(src, dst, follow_symlinks=False)
    # sockets, FIFOs and devices (e.g. qBittorrent ipc-socket) are runtime-only: skipped


def snapshot():
    last = None
    for attempt in range(1, 4):
        shutil.rmtree(stage, ignore_errors=True)
        databases.clear()
        try:
            shutil.copytree("/source", stage, symlinks=True, ignore=ignore, copy_function=copy_file)
            break
        except Exception as exc:  # noqa: BLE001 - retry, then fail closed
            last = exc
            print(f"attempt {attempt}: {exc}", file=sys.stderr)
            time.sleep(5)
    else:
        raise SystemExit(f"no consistent copy after 3 attempts: {last}")
    if not any(stage.iterdir()):
        raise SystemExit("source produced an empty copy")
    for path in [stage, *stage.rglob("*")]:
        os.lchown(path, 1004, 65534)
    print(f"snapshot ok: {len(databases)} SQLite database(s) via backup API")


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
