"""Materialize Git-owned Backrest plans with Secret-owned credentials."""

import base64
import json
import os
from pathlib import Path

os.umask(0o077)
state = Path("/state")
for name in ["data", "exports"]:
    (state / name).mkdir(mode=0o700, parents=True, exist_ok=True)
cluster = os.environ["CLUSTER_NAME"]
repository = Path("/nas") / cluster / "backrest" / "repository"
repository.mkdir(mode=0o700, parents=True, exist_ok=True)
config = json.loads(Path("/settings/config.json").read_text())
password = os.environ["BACKREST_REPOSITORY_PASSWORD"]
hashed = os.environ["BACKREST_ADMIN_PASSWORD_BCRYPT"]
if not password or not base64.b64decode(hashed, validate=True).startswith(b"$2"):
    raise SystemExit("Backrest credentials are missing or invalid")
config["auth"] = {
    "disabled": False,
    "users": [{"name": "admin", "passwordBcrypt": hashed}],
}
for repo in config["repos"]:
    repo["password"] = password
    repo["hooks"] = [
        {
            "conditions": ["CONDITION_ANY_ERROR", "CONDITION_SNAPSHOT_WARNING"],
            "actionSlack": {"webhookUrl": os.environ["SLACK_WEBHOOK_MONITORING"]},
        }
    ]
existing = state / "config.json"
if existing.exists():
    previous = json.loads(existing.read_text())
    config["modno"] = previous.get("modno", 0) + 1
    if "sync" in previous:
        config["sync"] = previous["sync"]
    config["version"] = previous.get("version", 5)
    for repo in config["repos"]:
        old = next(
            (
                item
                for item in previous.get("repos", [])
                if item["id"] == repo["id"] and item["uri"] == repo["uri"]
            ),
            None,
        )
        if old and old.get("guid"):
            repo["guid"] = old["guid"]
            repo["autoInitialize"] = False
staged = state / ".config.json.new"
staged.write_text(json.dumps(config, indent=2) + "\n")
staged.chmod(0o600)
staged.replace(existing)
