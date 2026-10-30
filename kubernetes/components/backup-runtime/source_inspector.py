"""Record the exact ready source pod/image before a native database export."""

import datetime
import json
import os
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request


def main():
    namespace = os.environ["POD_NAMESPACE"]
    selector = os.environ["SOURCE_SELECTOR"]
    container = os.environ["SOURCE_CONTAINER"]
    token_root = Path("/var/run/backup-api")
    context = ssl.create_default_context(cafile=str(token_root / "ca.crt"))
    query = urllib.parse.urlencode({"labelSelector": selector})
    request = urllib.request.Request(
        f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/pods?{query}",
        headers={
            "Authorization": "Bearer " + (token_root / "token").read_text().strip()
        },
    )
    try:
        with urllib.request.urlopen(request, context=context, timeout=20) as response:
            pods = json.load(response)["items"]
    except (urllib.error.URLError, OSError):
        raise SystemExit(
            "Source pod inspection failed; API credential/response suppressed"
        ) from None
    ready = [
        p
        for p in pods
        if not p["metadata"].get("deletionTimestamp")
        and any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in p["status"].get("conditions", [])
        )
    ]
    if len(ready) != 1:
        raise SystemExit(
            "Expected exactly one ready database source; refusing ambiguous export"
        )
    pod = ready[0]
    status = next(
        (
            c
            for c in pod["status"].get("containerStatuses", [])
            if c["name"] == container
        ),
        None,
    )
    if (
        status is None
        or not status.get("ready")
        or "@sha256:" not in status.get("imageID", "")
    ):
        raise SystemExit(
            "Source database container/digest is not ready or identifiable"
        )
    source = {
        "format": 1,
        "app": os.environ["BACKUP_APP"],
        "cluster": os.environ["BACKUP_CLUSTER"],
        "namespace": namespace,
        "pod": pod["metadata"]["name"],
        "pod_uid": pod["metadata"]["uid"],
        "node": pod["spec"]["nodeName"],
        "container": container,
        "image": status["image"],
        "image_id": status["imageID"],
        "inspected_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    stage = Path("/stage")
    stage.mkdir(mode=0o700, exist_ok=True)
    (stage / "source.json").write_text(json.dumps(source, sort_keys=True) + "\n")
    (stage / "source-ip").write_text(pod["status"]["podIP"] + "\n")
    print(
        f"Recorded exact source/digest for {namespace}/{source['app']}; no application data or credentials printed"
    )


if __name__ == "__main__":
    main()
