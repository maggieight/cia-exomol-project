"""Used to update the existing formal output"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import __version__
from .build_context import BuildContext
from .reports import sha256_file
from .validation import validate_release
from .versioning import validate_version
from .writers import build_release_content


def file_manifest(root: Path) -> list[dict[str, Any]]:
    """Return a stable path, type, size, and SHA-256 manifest."""
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        suffix = path.suffix.lower()
        file_type = "cia" if suffix == ".cia" else "json" if suffix == ".json" else "other"
        entries.append({
            "relative_path": path.relative_to(root).as_posix(),
            "file_type": file_type,
            "file_size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return entries


def manifest_sha256(entries: list[dict[str, Any]]) -> str:
    """Hash a stable file manifest independently of its storage path."""
    payload = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unique_directory(parent: Path, base: str) -> Path:
    candidate = parent / base
    index = 1
    while candidate.exists():
        candidate = parent / f"{base}-{index}"
        index += 1
    return candidate


def _source_inventory(project_root: Path) -> list[dict[str, Any]]:
    paths = []
    for relative in ("input", "source_data/non_hitran", "metadata"):
        root = project_root / relative
        paths.extend(path for path in root.rglob("*") if path.is_file())
    return [
        {
            "relative_path": path.relative_to(project_root).as_posix(),
            "file_size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(set(paths))
    ]


def publish_release(
    input_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    reports_root: Path,
    backups_root: Path,
    examples_dir: Path,
    context: BuildContext,
) -> tuple[dict[str, Any], Path]:
    """Build, validate, back up, atomically publish, and revalidate a release."""
    input_dir = input_dir.resolve()
    metadata_dir = metadata_dir.resolve()
    output_dir = output_dir.resolve()
    reports_root = reports_root.resolve()
    backups_root = backups_root.resolve()
    examples_dir = examples_dir.resolve()
    if not output_dir.is_dir() or not any(output_dir.iterdir()):
        raise FileNotFoundError(f"existing formal output is required: {output_dir}")
    project_root = output_dir.parent.resolve()
    for required in (input_dir, metadata_dir, examples_dir):
        required.resolve().relative_to(project_root)
    master_path = output_dir / "cia.all.json"
    if not master_path.is_file():
        raise FileNotFoundError(f"existing formal output has no master file: {master_path}")
    try:
        previous_version = json.loads(
            master_path.read_text(encoding="utf-8")
        )["version"]
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        raise ValueError(f"cannot read existing output version: {master_path}") from exc
    validate_version(previous_version, "existing output version")
    previous_files = file_manifest(output_dir)
    previous_sha = manifest_sha256(previous_files)
    staging_root = Path(tempfile.mkdtemp(prefix=".release-staging-", dir=project_root))
    staging_output = staging_root / "output"
    staging_reports = staging_root / "reports"
    backup_dir: Path | None = None
    switched = False
    try:
        summary, validation, _ = build_release_content(
            input_dir, metadata_dir, staging_output, staging_reports,
            context, examples_dir,
        )
        if not summary["strict_build_ready"] or validation["summary"]["errors"]:
            raise RuntimeError("candidate strict validation failed")
        candidate_validation = validate_release(
            input_dir, metadata_dir, staging_output, examples_dir
        )
        if not candidate_validation["valid"]:
            raise RuntimeError("candidate deterministic rebuild validation failed")
        candidate_files = file_manifest(staging_output)
        candidate_sha = manifest_sha256(candidate_files)

        backups_root.mkdir(parents=True, exist_ok=True)
        backup_dir = _unique_directory(backups_root, previous_version)
        output_dir.rename(backup_dir)
        staging_output.rename(output_dir)
        switched = True

        final_files = file_manifest(output_dir)
        final_sha = manifest_sha256(final_files)
        if candidate_files != final_files:
            raise RuntimeError("published output differs from validated candidate")
        post_validation = validate_release(
            input_dir, metadata_dir, output_dir, examples_dir
        )
        if not post_validation["valid"]:
            raise RuntimeError("post-release strict validation failed")

        release_reports = _unique_directory(reports_root / "release", context.version)
        release_reports.mkdir(parents=True, exist_ok=False)
        for report in sorted(staging_reports.iterdir()):
            report.rename(release_reports / report.name)
        (release_reports / "previous_output_manifest.json").write_text(
            json.dumps(previous_files, indent=2) + "\n", encoding="utf-8"
        )
        (release_reports / "post_release_validation.json").write_text(
            json.dumps(post_validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        master = json.loads((output_dir / "cia.all.json").read_text(encoding="utf-8"))
        two_column = three_column = 0
        for path in output_dir.glob("*/*.cia"):
            columns = len(path.read_text(encoding="utf-8").splitlines()[0].split())
            two_column += columns == 2
            three_column += columns == 3
        source_inventory = _source_inventory(project_root)
        manifest = {
            "release_id": f"CIA-{context.version}",
            "version": context.version,
            "generated_at": datetime.now(ZoneInfo(context.timezone)).isoformat(timespec="seconds"),
            "project_path": ".",
            "build_command": "cia-pipeline release --input input --metadata metadata --output output --reports reports --backups releases/backups --examples examples --strict",
            "build_timezone": context.timezone,
            "python_version": platform.python_version(),
            "package_version": __version__,
            "source_inventory": source_inventory,
            "pair_count": master["pair_count"],
            "dataset_count": master["dataset_count"],
            "recommended_dataset_count": master["recommended_dataset_count"],
            "supplementary_dataset_count": master["supplementary_dataset_count"],
            "cia_file_count": two_column + three_column,
            "two_column_cia_count": two_column,
            "three_column_cia_count": three_column,
            "total_file_count": len(final_files),
            "files": final_files,
            "test_result": "passed",
            "strict_validation_result": "passed",
            "staging_manifest_sha256": candidate_sha,
            "final_output_manifest_sha256": final_sha,
            "staging_final_comparison": "identical",
            "backup_location": backup_dir.relative_to(project_root).as_posix(),
            "previous_output_manifest_sha256": previous_sha,
            "release_errors": 0,
            "release_warnings": summary.get("warnings_by_category", {}),
            "skipped_records": summary["deliberately_skipped_block_count"],
            "blocking_errors": summary["warnings_by_category"]["blocking"],
            "numeric_mismatches": validation["summary"]["numeric_mismatches"],
            "broken_references": validation["summary"]["broken_references"],
            "filename_collisions": validation["summary"]["filename_collisions"],
            "orphan_count": validation["summary"]["orphan_dataset_json"] + validation["summary"]["orphan_cia_files"],
            "rollback_performed": False,
        }
        (release_reports / "release_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return manifest, release_reports
    except Exception:
        if switched and backup_dir is not None and backup_dir.exists():
            failed_output = staging_root / "failed-output"
            if output_dir.exists():
                output_dir.rename(failed_output)
            backup_dir.rename(output_dir)
            restored = file_manifest(output_dir)
            if restored != previous_files:
                raise RuntimeError("release failed and previous output restoration did not match")
        raise
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
