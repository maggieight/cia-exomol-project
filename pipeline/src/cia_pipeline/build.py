"""Used for the first generation of formal output"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from .build_context import BuildContext
from .reports import write_release_manifest
from .writers import build_release_content


def build_release(
    input_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    reports_dir: Path,
    examples_dir: Path,
    context: BuildContext,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build, strictly validate, and atomically publish a CIA release."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    reports_dir.mkdir(parents=True, exist_ok=True)
    if any(reports_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty reports: {reports_dir}")
    project_root = output_dir.parent
    staging_root = Path(
        tempfile.mkdtemp(prefix=".build-staging-", dir=project_root)
    )
    staging_output = staging_root / "output"
    staging_reports = staging_root / "reports"
    try:
        summary, validation, _ = build_release_content(
            input_dir,
            metadata_dir,
            staging_output,
            staging_reports,
            context,
            examples_dir,
        )
        if not summary["strict_build_ready"] or validation["summary"]["errors"]:
            raise RuntimeError("strict release validation failed")
        write_release_manifest(staging_output, staging_reports, context)
        staging_output.rename(output_dir)
        for report in sorted(staging_reports.iterdir()):
            report.rename(reports_dir / report.name)
        return summary, validation
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
