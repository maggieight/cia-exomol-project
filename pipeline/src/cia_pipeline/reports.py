from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .build_context import BuildContext


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_release_manifest(
    output_dir: Path, reports_dir: Path, context: BuildContext
) -> dict[str, object]:
    """Write deterministic file hashes plus release-environment metadata."""
    files = [
        {
            "relative_path": path.relative_to(output_dir).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(path for path in output_dir.rglob("*") if path.is_file())
    ]
    manifest: dict[str, object] = {
        "project_version": __version__,
        "build_version": context.version,
        "build_timezone": context.timezone,
        "build_timestamp": datetime.now(
            ZoneInfo(context.timezone)
        ).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "package_version": __version__,
        "pair_count": len(list(output_dir.glob("*/*.json"))) - len(
            list(output_dir.glob("*/*_*.json"))
        ),
        "dataset_count": len(list(output_dir.glob("*/*_*.json"))),
        "cia_count": len(list(output_dir.glob("*/*.cia"))),
        "files": files,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "release_manifest.json"
    json_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest
