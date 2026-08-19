"""Perform deterministic verification on the existing output"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .build_context import BuildContext
from .reports import sha256_file
from .writers import build_release_content


def validate_release(
    input_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    examples_dir: Path,
) -> dict[str, Any]:
    """Validate an existing release against a fresh deterministic rebuild."""
    master = json.loads((output_dir / "cia.all.json").read_text(encoding="utf-8"))
    build_date = datetime.strptime(master["version"], "%Y%m%d").date()
    context = BuildContext.from_date(build_date)
    temporary_root = Path(tempfile.mkdtemp(prefix="cia-validate-"))
    try:
        canonical = temporary_root / "output"
        reports = temporary_root / "reports"
        _, internal, _ = build_release_content(
            input_dir, metadata_dir, canonical, reports, context, examples_dir
        )
        actual = {
            path.relative_to(output_dir).as_posix(): sha256_file(path)
            for path in output_dir.rglob("*")
            if path.is_file()
        }
        expected = {
            path.relative_to(canonical).as_posix(): sha256_file(path)
            for path in canonical.rglob("*")
            if path.is_file()
        }
        missing = sorted(set(expected) - set(actual))
        orphan = sorted(set(actual) - set(expected))
        changed = sorted(
            path for path in set(actual) & set(expected) if actual[path] != expected[path]
        )
        valid = (
            internal["summary"]["errors"] == 0
            and not missing
            and not orphan
            and not changed
        )
        return {
            "valid": valid,
            "missing_files": missing,
            "orphan_files": orphan,
            "content_mismatches": changed,
            "internal_validation": internal,
        }
    finally:
        shutil.rmtree(temporary_root)
