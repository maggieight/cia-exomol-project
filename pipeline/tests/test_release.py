from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import cia_pipeline.release as release
from cia_pipeline.build_context import BuildContext


def setup_project(tmp_path: Path):
    for name in ("input", "metadata", "examples"):
        (tmp_path / name).mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / "old.txt").write_text("old")
    (output / "cia.all.json").write_text(json.dumps({"version": "20260802"}))
    return output


def fake_build(_input, _metadata, output, reports, context, _examples):
    output.mkdir(parents=True)
    reports.mkdir(parents=True)
    master = {
        "id": "CIA.master",
        "version": context.version,
        "pair_count": 0,
        "dataset_count": 0,
        "recommended_dataset_count": 0,
        "supplementary_dataset_count": 0,
        "pairs": [],
    }
    (output / "cia.all.json").write_text(json.dumps(master))
    (reports / "final_validation.json").write_text("{}")
    summary = {
        "strict_build_ready": True,
        "warnings_by_category": {"blocking": 0},
        "deliberately_skipped_block_count": 0,
    }
    validation = {
        "summary": {
            "errors": 0,
            "numeric_mismatches": 0,
            "broken_references": 0,
            "filename_collisions": 0,
            "orphan_dataset_json": 0,
            "orphan_cia_files": 0,
        }
    }
    return summary, validation, []


def test_success_creates_backup_and_publishes_atomically(tmp_path: Path, monkeypatch) -> None:
    output = setup_project(tmp_path)
    monkeypatch.setattr(release, "build_release_content", fake_build)
    monkeypatch.setattr(release, "validate_release", lambda *args: {"valid": True})
    manifest, reports = release.publish_release(
        tmp_path / "input",
        tmp_path / "metadata",
        output,
        tmp_path / "reports",
        tmp_path / "releases/backups",
        tmp_path / "examples",
        BuildContext.from_date(date(2026, 8, 3)),
    )
    assert (output / "cia.all.json").is_file() and not (output / "old.txt").exists()
    backup = tmp_path / manifest["backup_location"]
    assert (backup / "old.txt").read_text() == "old"
    assert backup.name == "20260802"
    assert (reports / "release_manifest.json").is_file()


def test_candidate_validation_failure_does_not_replace_output(tmp_path: Path, monkeypatch) -> None:
    output = setup_project(tmp_path)
    monkeypatch.setattr(release, "build_release_content", fake_build)
    monkeypatch.setattr(release, "validate_release", lambda *args: {"valid": False})
    with pytest.raises(RuntimeError, match="candidate"):
        release.publish_release(
            tmp_path / "input",
            tmp_path / "metadata",
            output,
            tmp_path / "reports",
            tmp_path / "backups",
            tmp_path / "examples",
            BuildContext.from_date(date(2026, 8, 3)),
        )
    assert (output / "old.txt").read_text() == "old"


def test_post_validation_failure_restores_old_output(tmp_path: Path, monkeypatch) -> None:
    output = setup_project(tmp_path)
    results = iter(({"valid": True}, {"valid": False}))
    monkeypatch.setattr(release, "build_release_content", fake_build)
    monkeypatch.setattr(release, "validate_release", lambda *args: next(results))
    with pytest.raises(RuntimeError, match="post-release"):
        release.publish_release(
            tmp_path / "input",
            tmp_path / "metadata",
            output,
            tmp_path / "reports",
            tmp_path / "backups",
            tmp_path / "examples",
            BuildContext.from_date(date(2026, 8, 3)),
        )
    assert (output / "old.txt").read_text() == "old"
    assert json.loads((output / "cia.all.json").read_text())["version"] == "20260802"


def test_existing_backup_name_is_not_overwritten(tmp_path: Path) -> None:
    parent = tmp_path / "backups"
    parent.mkdir()
    (parent / "20260803").mkdir()
    assert release._unique_directory(parent, "20260803").name == "20260803-1"
