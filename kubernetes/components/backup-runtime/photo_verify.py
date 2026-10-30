"""Validate every DB-referenced original in a restored tree, never the live share."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def verify(root):
    root = Path(root).resolve(strict=True)
    metadata = root / ".backup-metadata"
    record = json.loads((metadata / "photo-set.json").read_bytes())
    references = (metadata / "original-refs.jsonl").read_bytes()
    if record.get("format") != 1 or record.get("kind") != "immich-photo-set":
        raise RuntimeError("Unsupported photo recovery-set format")
    if hashlib.sha256(references).hexdigest() != record["references_sha256"]:
        raise RuntimeError("Photo reference manifest checksum differs")
    checked = {}
    assets = 0
    canonical_references = []
    for line in references.splitlines():
        entry = json.loads(line)
        canonical_references.append(entry)
        path, checksum = entry["path"], entry["sha1"]
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{40}", checksum):
            raise RuntimeError("Original has no supported checksum")
        if path.startswith("/external-library/"):
            relative = "library/" + path.removeprefix("/external-library/")
        elif path.startswith("/data/"):
            relative = path.removeprefix("/data/")
        else:
            raise RuntimeError("Original path is outside the captured subtree")
        parts = PurePosixPath(relative)
        if parts.is_absolute() or ".." in parts.parts or "\x00" in relative:
            raise RuntimeError("Unsafe original path in photo reference manifest")
        candidate = root.joinpath(*parts.parts)
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root) or candidate.is_symlink() or not resolved.is_file():
            raise RuntimeError("Original is missing or escapes the restored tree")
        if relative not in checked:
            with resolved.open("rb") as source:
                checked[relative] = hashlib.file_digest(source, "sha1").hexdigest()
        if checked[relative] != checksum:
            raise RuntimeError("Restored original differs from the matching database checksum")
        assets += 1
    return {"referenced_assets": assets, "unique_originals_verified": len(checked), "phase": record["phase"], "reference_sha256": record["references_sha256"], "canonical_reference_sha256": hashlib.sha256(json.dumps(canonical_references, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1]), sort_keys=True))
