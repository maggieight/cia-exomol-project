"""validate the output flow"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .build_context import BuildContext
from .master import MASTER_FILENAME, MASTER_ID, pair_json_paths
from .versioning import is_valid_version


def _safe_relative_posix(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not value.startswith("/")
        and "://" not in value
        and path.as_posix() == value
    )


def validate_master(output_root: Path, context: BuildContext) -> dict[str, Any]:
    master_path = output_root / MASTER_FILENAME
    errors: list[dict[str, Any]] = []
    broken_pair_files: list[str] = []
    broken_recommended_metadata: list[str] = []
    version_mismatches: list[str] = []
    reachable_pair_json: set[Path] = set()
    reachable_dataset_json: set[Path] = set()
    reachable_cia: set[Path] = set()

    if not master_path.exists():
        return {
            "valid": False,
            "errors": [{"problem": f"missing {MASTER_FILENAME}"}],
            "pair_count": 0,
        }
    if master_path.name != MASTER_FILENAME:
        errors.append({"problem": "master filename is not cia.all.json"})
    try:
        master = json.loads(master_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "valid": False,
            "errors": [{"problem": f"cannot read master: {exc}"}],
            "pair_count": 0,
        }
    if master.get("id") != MASTER_ID:
        errors.append({"problem": "master id is not CIA.master"})
    version = master.get("version")
    if not is_valid_version(version):
        errors.append({"problem": "master version is not a valid YYYYMMDD string"})
    if version != context.version:
        errors.append({"problem": "master version differs from BuildContext"})
    pairs = master.get("pairs")
    if not isinstance(pairs, list):
        pairs = []
        errors.append({"problem": "master pairs must be an array"})
    formulas = [item.get("formula") for item in pairs if isinstance(item, dict)]
    sorted_formulas = sorted(
        formulas, key=lambda value: "" if value is None else str(value)
    )
    if formulas != sorted_formulas:
        errors.append({"problem": "master pairs are not sorted by formula"})
    duplicates = [
        formula for formula, count in Counter(formulas).items() if count > 1
    ]
    if duplicates:
        errors.append({"problem": f"duplicate collision pairs: {duplicates}"})
    if master.get("pair_count") != len(pairs):
        errors.append({"problem": "master pair_count does not equal len(pairs)"})

    total_dataset_count = 0
    actual_recommended_count = 0
    actual_supplementary_count = 0
    for item in pairs:
        formula = item.get("formula")
        slug = item.get("slug")
        if not formula:
            errors.append({"problem": "master collision_pair.formula is empty"})
        if not slug:
            errors.append({"problem": f"{formula}: collision_pair.slug is empty"})
        pair_file = item.get("pair_file")
        if not _safe_relative_posix(pair_file):
            errors.append({"problem": f"{formula}: unsafe pair_file {pair_file!r}"})
            continue
        if not pair_file.endswith(".json"):
            errors.append({"problem": f"{formula}: pair_file is not JSON"})
        pair_path = output_root / PurePosixPath(pair_file)
        if not pair_path.is_file():
            broken_pair_files.append(pair_file)
            errors.append({"problem": f"{formula}: pair_file does not exist"})
            continue
        reachable_pair_json.add(pair_path.resolve())
        pair_json = json.loads(pair_path.read_text(encoding="utf-8"))
        pair_collision = pair_json.get("collision_pair", {})
        if pair_collision.get("formula") != formula:
            errors.append({"problem": f"{formula}: pair formula mismatch"})
        if pair_collision.get("slug") != slug:
            errors.append({"problem": f"{formula}: pair slug mismatch"})
        pair_version = pair_json.get("version")
        if not is_valid_version(pair_version):
            errors.append({"problem": f"{formula}: invalid pair version"})
        if pair_version != version:
            version_mismatches.append(pair_file)
            errors.append({"problem": f"{formula}: pair version mismatch"})
        datasets = pair_json.get("datasets", [])
        total_dataset_count += len(datasets)
        if item.get("dataset_count") != len(datasets):
            errors.append({"problem": f"{formula}: dataset_count mismatch"})
        dataset_by_id = {
            dataset.get("dataset_id"): dataset for dataset in datasets
        }
        pair_recommended = pair_json.get("recommended_dataset")
        master_recommended = item.get("recommended_dataset")
        if pair_recommended is None:
            if master_recommended is not None:
                errors.append(
                    {"problem": f"{formula}: null recommendation has metadata pointer"}
                )
        else:
            actual_recommended_count += 1
            if not isinstance(master_recommended, dict):
                errors.append(
                    {"problem": f"{formula}: recommended pointer is missing"}
                )
            elif master_recommended.get("dataset") != pair_recommended:
                errors.append(
                    {"problem": f"{formula}: recommended dataset mismatch"}
                )
            if pair_recommended not in dataset_by_id:
                errors.append(
                    {"problem": f"{formula}: recommended ID absent from datasets[]"}
                )
            if isinstance(master_recommended, dict):
                recommended_path = master_recommended.get("metadata_file")
                if not _safe_relative_posix(recommended_path):
                    broken_recommended_metadata.append(str(recommended_path))
                    errors.append(
                        {
                            "problem": f"{formula}: unsafe recommended metadata path"
                        }
                    )
                elif not (output_root / recommended_path).is_file():
                    broken_recommended_metadata.append(recommended_path)
                    errors.append(
                        {"problem": f"{formula}: recommended metadata is missing"}
                    )
        for dataset_link in datasets:
            dataset_version = dataset_link.get("dataset_version")
            if not is_valid_version(dataset_version):
                errors.append(
                    {
                        "problem": f"{formula}: invalid or missing datasets[].dataset_version"
                    }
                )
            elif dataset_version != version:
                version_mismatches.append(
                    f"{pair_file}#{dataset_link.get('dataset_id')}"
                )
                errors.append(
                    {"problem": f"{formula}: dataset pointer version mismatch"}
                )
            metadata_name = dataset_link.get("metadata_file")
            if not _safe_relative_posix(metadata_name) or "/" in metadata_name:
                errors.append(
                    {"problem": f"{formula}: unsafe pair metadata_file {metadata_name!r}"}
                )
                continue
            dataset_path = pair_path.parent / metadata_name
            if not dataset_path.is_file():
                errors.append(
                    {"problem": f"{formula}: dataset metadata is missing: {metadata_name}"}
                )
                continue
            reachable_dataset_json.add(dataset_path.resolve())
            dataset_json = json.loads(dataset_path.read_text(encoding="utf-8"))
            dataset = dataset_json.get("dataset", {})
            if dataset.get("id") != dataset_link.get("dataset_id"):
                errors.append(
                    {"problem": f"{formula}: dataset.id linkage mismatch"}
                )
            if (
                dataset_json.get("collision_pair", {}).get("formula")
                != formula
            ):
                errors.append(
                    {"problem": f"{formula}: dataset collision pair mismatch"}
                )
            scientific_version = dataset.get("version")
            if not is_valid_version(scientific_version):
                errors.append(
                    {"problem": f"{formula}: invalid dataset JSON version"}
                )
            if scientific_version != version:
                version_mismatches.append(
                    dataset_path.relative_to(output_root).as_posix()
                )
                errors.append(
                    {"problem": f"{formula}: dataset version mismatch"}
                )
            if scientific_version != dataset_version:
                errors.append(
                    {
                        "problem": f"{formula}: pair dataset_version differs from dataset JSON"
                    }
                )
            if "recommendation_status" in dataset:
                errors.append(
                    {"problem": f"{formula}: dataset duplicates pair recommendation status"}
                )
            is_recommended_dataset = dataset_link.get("dataset_id") == pair_recommended
            if not is_recommended_dataset:
                actual_supplementary_count += 1
            if is_recommended_dataset:
                if isinstance(master_recommended, dict):
                    if master_recommended.get("dataset_version") != dataset_version:
                        errors.append(
                            {
                                "problem": f"{formula}: recommended dataset_version mismatch"
                            }
                        )
                    if not is_valid_version(
                        master_recommended.get("dataset_version")
                    ):
                        errors.append(
                            {
                                "problem": f"{formula}: invalid recommended dataset_version"
                            }
                        )
                    recommended_metadata = master_recommended.get("metadata_file")
                    expected_metadata = PurePosixPath(
                        pair_path.parent.name, metadata_name
                    ).as_posix()
                    if recommended_metadata != expected_metadata:
                        errors.append(
                            {
                                "problem": f"{formula}: recommended metadata pointer mismatch"
                            }
                        )
            for cia_link in dataset.get(
                "collision_induced_absorption_xsecs", {}
            ).get("files", []):
                cia_name = cia_link.get("filename")
                if not _safe_relative_posix(cia_name) or "/" in cia_name:
                    errors.append(
                        {"problem": f"{formula}: unsafe CIA filename {cia_name!r}"}
                    )
                    continue
                cia_path = dataset_path.parent / cia_name
                if not cia_path.is_file():
                    errors.append(
                        {"problem": f"{formula}: CIA file is missing: {cia_name}"}
                    )
                else:
                    reachable_cia.add(cia_path.resolve())

    actual_pair_json = {path.resolve() for path in pair_json_paths(output_root)}
    actual_dataset_json = {
        path.resolve()
        for path in output_root.glob("*/*.json")
        if path.resolve() not in actual_pair_json
    }
    actual_cia = {path.resolve() for path in output_root.glob("*/*.cia")}
    orphan_pair = sorted(
        path.relative_to(output_root.resolve()).as_posix()
        for path in actual_pair_json - reachable_pair_json
    )
    orphan_dataset = sorted(
        path.relative_to(output_root.resolve()).as_posix()
        for path in actual_dataset_json - reachable_dataset_json
    )
    orphan_cia = sorted(
        path.relative_to(output_root.resolve()).as_posix()
        for path in actual_cia - reachable_cia
    )
    for kind, values in (
        ("pair JSON", orphan_pair),
        ("dataset JSON", orphan_dataset),
        ("CIA", orphan_cia),
    ):
        if values:
            errors.append({"problem": f"orphan {kind} files", "files": values})
    if len(actual_pair_json) != len(pairs):
        errors.append(
            {
                "problem": "master pair count differs from actual pair JSON count"
            }
        )
    if master.get("dataset_count") != total_dataset_count:
        errors.append({"problem": "master dataset_count mismatch"})
    if master.get("recommended_dataset_count") != actual_recommended_count:
        errors.append({"problem": "master recommended_dataset_count mismatch"})
    if master.get("supplementary_dataset_count") != actual_supplementary_count:
        errors.append({"problem": "master supplementary_dataset_count mismatch"})
    if actual_recommended_count + actual_supplementary_count != total_dataset_count:
        errors.append(
            {"problem": "recommended plus supplementary does not equal total datasets"}
        )
    return {
        "valid": not errors,
        "errors": errors,
        "pair_count": len(pairs),
        "actual_pair_json_count": len(actual_pair_json),
        "recommended_pair_count": sum(
            item.get("recommended_dataset") is not None for item in pairs
        ),
        "supplementary_only_pair_count": sum(
            item.get("recommended_dataset") is None for item in pairs
        ),
        "null_recommended_pairs": [
            item["formula"]
            for item in pairs
            if item.get("recommended_dataset") is None
        ],
        "broken_pair_files": broken_pair_files,
        "broken_recommended_metadata": broken_recommended_metadata,
        "orphan_pair_json": orphan_pair,
        "orphan_dataset_json": orphan_dataset,
        "orphan_cia_files": orphan_cia,
        "cross_file_version_mismatches": sorted(set(version_mismatches)),
        "reachable_dataset_json_count": len(reachable_dataset_json),
        "reachable_cia_count": len(reachable_cia),
    }
