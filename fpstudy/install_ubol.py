"""Fetch the version-pinned official uBlock Origin Lite Chromium build."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "data" / "extensions" / "ubol"
METADATA = ASSET_DIR / "source.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    archive_path = ASSET_DIR / metadata["asset"]
    if archive_path.is_file():
        payload = archive_path.read_bytes()
    else:
        request = urllib.request.Request(
            metadata["source_url"], headers={"User-Agent": "fpstudy-research"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()

    actual_hash = sha256(payload)
    if actual_hash != metadata["sha256"]:
        raise SystemExit(
            f"uBOL archive hash mismatch: expected {metadata['sha256']}, got {actual_hash}"
        )
    archive_path.write_bytes(payload)

    staging = ASSET_DIR / ".unpacked-staging"
    destination = ASSET_DIR / "unpacked"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SystemExit(f"Unsafe path in uBOL archive: {member.filename}")
        archive.extractall(staging)

    manifest_path = staging / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("manifest_version") != metadata["manifest_version"]
        or manifest.get("version") != metadata["release"]
    ):
        raise SystemExit("Downloaded extension manifest does not match the pinned metadata")

    shutil.rmtree(destination, ignore_errors=True)
    staging.rename(destination)
    print(
        f"Installed {metadata['project']} {metadata['release']} "
        f"at {destination.relative_to(ROOT)} (SHA-256 verified)"
    )


if __name__ == "__main__":
    main()
