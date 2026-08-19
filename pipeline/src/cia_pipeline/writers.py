"""Write the input in ExoMol style output"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .grouping import safe_id
from .extradata import load_extra, validate_spectral_regions
from .build_context import BuildContext
from .hitran_parser import parse_file, parse_repository_version
from .metadata import SHARED_HITRAN_SOURCE_IDS, load_metadata
from .models import (
    ABSOLUTE_UNCERTAINTY_COLUMN_SCHEMA,
    STANDARD_COLUMN_SCHEMA,
    CIABlock,
    MetadataRegistry,
)
from .naming import dataset_metadata_filename, proposed_cia_filenames
from .master import MASTER_FILENAME, write_master
from .master_validation import validate_master

REPOSITORY_NAME = "HITRAN CIA"


@dataclass
class DatasetGroup:
    pair: str
    dataset_id: str
    collection: str
    recommended: bool
    blocks: list[CIABlock]


def dataset_source_keys(group: DatasetGroup) -> list[str]:
    """Return ordered dataset sources, adding shared provenance to HITRAN groups."""
    keys = sorted(
        {
            key
            for block in group.blocks
            for key in block.citation_keys
            if key not in SHARED_HITRAN_SOURCE_IDS
        }
    )
    if group.collection in {"main", "sup"}:
        keys.extend(SHARED_HITRAN_SOURCE_IDS)
    return keys


def load_blocks(
    input_dir: Path, metadata_dir: Path
) -> tuple[list[CIABlock], MetadataRegistry]:
    registry = load_metadata(metadata_dir, strict=False)
    blocks: list[CIABlock] = []
    for relative, entry in sorted(registry.dataset_files.items()):
        if not relative.startswith(("main/", "sup/")):
            continue
        path = input_dir / relative
        parsed = parse_file(path, relative)
        version = parse_repository_version(path.name)
        for block in parsed:
            block.collection = relative.split("/", 1)[0]
            block.repository_version = version
            block.normalized_pair = entry.pair
            block.active_species_status = entry.active_species_status
            block.active_species = entry.active_species
            block.collider = entry.collider
            block.components = entry.components
            block.variant = entry.variant
            block.citation_keys = registry.references.get(block.reference_number, ())
            if block.header_pair.lower() != entry.pair.lower():
                block.warnings.append(
                    f"header pair {block.header_pair!r} differs from mapped pair {entry.pair!r}"
                )
            blocks.append(block)
    blocks.extend(load_extra(input_dir, registry))
    return blocks, registry


def group_blocks(blocks: list[CIABlock]) -> list[DatasetGroup]:
    grouped: dict[tuple[Any, ...], list[CIABlock]] = defaultdict(list)
    for block in blocks:
        if block.input_kind == "extradata":
            key = ("extra", block.normalized_pair, block.explicit_dataset_id)
        elif block.collection == "main":
            key = ("main", block.normalized_pair, block.repository_version)
        else:
            key = (
                "sup",
                block.normalized_pair,
                tuple(block.citation_keys),
            )
        grouped[key].append(block)
    result: list[DatasetGroup] = []
    for key, members in grouped.items():
        collection, pair = key[:2]
        if collection == "extra":
            dataset_id = members[0].explicit_dataset_id
        elif collection == "main":
            refs = {block.reference_number for block in members}
            citations = {key for block in members for key in block.citation_keys}
            files = {block.raw_relative_path for block in members}
            if len(refs) == len(citations) == len(files) == 1:
                dataset_id = next(iter(citations))
            else:
                dataset_id = f"hitran{members[0].repository_version}-main"
        else:
            dataset_id = "-".join(key[2])
        result.append(
            DatasetGroup(
                pair=pair,
                dataset_id=safe_id(dataset_id),
                collection=collection,
                recommended=(
                    members[0].recommendation_status == "recommended"
                    if collection == "extra"
                    else collection == "main"
                ),
                blocks=members,
            )
        )
    return sorted(
        result,
        key=lambda group: (
            group.pair.lower(),
            0 if group.recommended else 1,
            group.dataset_id,
        ),
    )


def _component_tokens(label: str) -> list[str]:
    if "--" in label:
        tokens = [part.strip() for part in label.split("--")]
    else:
        tokens = [part.strip() for part in label.split("-")]
    cleaned = []
    for token in tokens:
        lowered = token.lower()
        if lowered.startswith("eq-"):
            token = token[3:]
        elif lowered.startswith("n-"):
            token = token[2:]
        cleaned.append(token.lower())
    return cleaned


def audit_warnings(blocks: list[CIABlock]) -> dict[str, Any]:
    informational: list[dict[str, Any]] = []
    recoverable: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    sentinel_blocks: list[dict[str, Any]] = []
    header_mismatches: list[dict[str, Any]] = []
    endpoint_mismatches: list[dict[str, Any]] = []
    for block in blocks:
        if block.input_kind == "extradata":
            continue
        location = {
            "original_file": block.raw_relative_path,
            "header_line_number": block.header_line_number,
            "reference_number": block.reference_number,
            "temperature": block.temperature,
        }
        if block.resolution is None:
            spacing = None
            if len(block.points) > 1:
                spacing = (block.points[-1].wavenumber - block.points[0].wavenumber) / (
                    len(block.points) - 1
                )
            item = {
                **location,
                "source_resolution_raw": block.resolution_raw,
                "output_resolution": None,
                "calculated_spacing": spacing,
                "classification": "informational",
                "note": "HITRAN sentinel retained as null; calculated spacing is diagnostic only",
            }
            sentinel_blocks.append(item)
            informational.append({"type": "resolution_sentinel", **item})
        if block.header_pair.lower() != block.normalized_pair.lower():
            raw_components = sorted(_component_tokens(block.header_pair))
            mapped_components = sorted(_component_tokens(block.normalized_pair))
            safe = raw_components == mapped_components
            item = {
                **location,
                "raw_header_pair": block.header_pair,
                "dataset_map_pair": block.normalized_pair,
                "canonical_pair": block.normalized_pair if safe else None,
                "raw_components": raw_components,
                "mapped_components": mapped_components,
                "classification": "informational" if safe else "blocking",
            }
            header_mismatches.append(item)
            (informational if safe else blocking).append(
                {"type": "header_pair_label_mismatch", **item}
            )
        if block.points and (
            block.points[0].wavenumber != block.min_wavenumber
            or block.points[-1].wavenumber != block.max_wavenumber
        ):
            monotonic = all(
                later.wavenumber > earlier.wavenumber
                for earlier, later in zip(block.points, block.points[1:])
            )
            actual_first_decimal = Decimal(block.points[0].wavenumber_text)
            actual_last_decimal = Decimal(block.points[-1].wavenumber_text)
            header_min_decimal = Decimal(str(block.min_wavenumber))
            header_max_decimal = Decimal(str(block.max_wavenumber))
            item = {
                **location,
                "header_minimum": block.min_wavenumber,
                "header_maximum": block.max_wavenumber,
                "actual_first": block.points[0].wavenumber,
                "actual_last": block.points[-1].wavenumber,
                "minimum_difference": str(
                    actual_first_decimal - header_min_decimal
                ),
                "maximum_difference": str(
                    actual_last_decimal - header_max_decimal
                ),
                "strictly_monotonic": monotonic,
                "classification": "recoverable" if monotonic else "blocking",
                "handling": "actual data-row endpoints are retained without modification",
            }
            endpoint_mismatches.append(item)
            (recoverable if monotonic else blocking).append(
                {"type": "endpoint_mismatch", **item}
            )
        if any(point.uncertainty is not None for point in block.points):
            informational.append(
                {
                    "type": "absolute_uncertainty_present",
                    **location,
                    "classification": "informational",
                    "handling": "third column retained as absolute uncertainty",
                }
            )
    return {
        "counts": {
            "informational": len(informational),
            "recoverable": len(recoverable),
            "blocking": len(blocking),
        },
        "informational": informational,
        "recoverable": recoverable,
        "blocking": blocking,
        "resolution_sentinels": sentinel_blocks,
        "header_pair_label_mismatches": header_mismatches,
        "endpoint_mismatches": endpoint_mismatches,
    }


def third_column_report(blocks: list[CIABlock]) -> dict[str, Any]:
    affected = [
        block
        for block in blocks
        if any(point.uncertainty is not None for point in block.points)
    ]
    file_indices: dict[tuple[str, int], int] = {}
    by_file: dict[str, list[CIABlock]] = defaultdict(list)
    for block in blocks:
        by_file[block.raw_relative_path].append(block)
    for filename, members in by_file.items():
        for index, block in enumerate(
            sorted(members, key=lambda item: item.header_line_number), start=1
        ):
            file_indices[(filename, block.header_line_number)] = index
    records = []
    for block in affected:
        third = [
            Decimal(point.uncertainty_text)
            for point in block.points
            if point.uncertainty_text is not None
        ]
        unique = set(third)
        rows = [
            {
                "raw": point.raw_line,
                "columns": [
                    point.wavenumber_text,
                    point.cia_coefficient_text,
                    *(
                        [point.uncertainty_text]
                        if point.uncertainty_text is not None
                        else []
                    ),
                ],
            }
            for point in block.points
        ]
        records.append(
            {
                "original_file": block.raw_relative_path,
                "block_index": file_indices[
                    (block.raw_relative_path, block.header_line_number)
                ],
                "header_line_number": block.header_line_number,
                "reference_number": block.reference_number,
                "temperature": block.temperature,
                "header": block.header_text,
                "header_description": block.description,
                "column_count": 3,
                "first_10_rows": rows[:10],
                "last_10_rows": rows[-10:],
                "third_column": {
                    "minimum": str(min(third)),
                    "maximum": str(max(third)),
                    "unique_value_count": len(unique),
                    "is_constant": len(unique) == 1,
                },
                "semantic_assessment": {
                    "status": "resolved_from_HITRAN_CIA_schema",
                    "evidence_from_header_or_comment": block.description,
                    "conclusion": (
                        "The third column is the absolute uncertainty of the CIA "
                        "absorption coefficient and uses the same units."
                    ),
                },
                "classification": "informational",
                "build_handling": "emitted unchanged as a three-column CIA file",
            }
        )
    return {
        "schema_version": 1,
        "affected_block_count": len(records),
        "status": "resolved_absolute_uncertainty" if records else "clear",
        "blocks": records,
    }


def _species_component(record: dict[str, Any]) -> dict[str, Any]:
    component = {
        "formula": record["formula"],
        "slug": record["slug"],
        "cas_registry_number": record["cas_registry_number"],
    }
    if "cas_registry_number_status" in record:
        component["cas_registry_number_status"] = record[
            "cas_registry_number_status"
        ]
    return component


def _collision_pair(group: DatasetGroup, registry: MetadataRegistry) -> dict[str, Any]:
    sample = group.blocks[0]
    if sample.collision_pair_record is not None:
        return sample.collision_pair_record
    slugs = (
        list(sample.components)
        if sample.components
        else [sample.active_species, sample.collider]
    )
    components = [_species_component(registry.species[slug]) for slug in slugs if slug]
    return {
        "formula": group.pair,
        "slug": group.pair.lower(),
        "active_species_status": sample.active_species_status,
        "active_species": sample.active_species,
        "collider": sample.collider,
        "components": components,
    }


def _json_write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _column_schemas(has_uncertainty: bool) -> dict[str, list[dict[str, str]]]:
    schemas = {"standard": STANDARD_COLUMN_SCHEMA}
    if has_uncertainty:
        schemas["with_absolute_uncertainty"] = (
            ABSOLUTE_UNCERTAINTY_COLUMN_SCHEMA
        )
    return schemas

"""main"""
def build_release_content(
    input_dir: Path,
    metadata_dir: Path,
    output_dir: Path,
    reports_dir: Path,
    context: BuildContext,
    examples_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    version = context.version
    blocks, registry = load_blocks(input_dir, metadata_dir)
    groups = group_blocks(blocks)
    warning_audit = audit_warnings(blocks)
    third_report = third_column_report(blocks)
    skipped_ids: set[tuple[str, int]] = set()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    manifest: list[dict[str, Any]] = []
    pair_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for group in groups:
        pair_dir = output_dir / group.pair
        pair_dir.mkdir(parents=True, exist_ok=True)
        successful = [
            block
            for block in group.blocks
            if (block.raw_relative_path, block.header_line_number) not in skipped_ids
        ]
        ordered = sorted(
            successful,
            key=lambda block: (
                block.temperature,
                block.points[0].wavenumber,
                block.points[-1].wavenumber,
                block.reference_number if block.reference_number is not None else -1,
                block.variant or "",
                block.raw_relative_path,
                block.header_line_number,
            ),
        )
        name_blocks = []
        for block in ordered:
            # Naming uses actual data endpoints for recoverable header mismatches.
            clone = CIABlock(**{**block.__dict__})
            clone.min_wavenumber = block.points[0].wavenumber
            clone.max_wavenumber = block.points[-1].wavenumber
            name_blocks.append(clone)
        cia_names = proposed_cia_filenames(group.pair, group.dataset_id, name_blocks)
        actual_min = min(block.points[0].wavenumber for block in ordered)
        actual_max = max(block.points[-1].wavenumber for block in ordered)
        temperatures = [block.temperature for block in ordered]
        metadata_name = dataset_metadata_filename(
            group.pair,
            group.dataset_id,
            actual_min,
            actual_max,
            min(temperatures),
            max(temperatures),
        )
        file_entries = []
        for block, cia_name in zip(ordered, cia_names):
            output_path = pair_dir / cia_name
            output_path.write_text(
                "\n".join(point.raw_line for point in block.points) + "\n",
                encoding="utf-8",
            )
            entry: dict[str, Any] = {
                "temperature": block.temperature,
                "wavenumber_resolution": block.resolution,
                "npoints": len(block.points),
                "filename": cia_name,
                "citation_keys": list(block.citation_keys),
            }
            if block.input_kind == "hitran":
                entry["reference_number"] = block.reference_number
            if block.input_kind == "hitran" and block.points[0].uncertainty is not None:
                entry["column_schema"] = "with_absolute_uncertainty"
            if block.input_kind == "extradata":
                if len(block.spectral_regions) > 1:
                    entry["spectral_regions"] = list(block.spectral_regions)
            if block.variant:
                entry["variant"] = block.variant
            file_entries.append(entry)
            manifest.append(
                {
                    "pair": group.pair,
                    "dataset_id": group.dataset_id,
                    "metadata_filename": metadata_name,
                    "cia_filename": cia_name,
                    "block": block,
                }
            )
        source_keys = dataset_source_keys(group)
        versions = sorted({block.repository_version for block in group.blocks if block.repository_version})
        variants = sorted({block.variant for block in group.blocks if block.variant})
        dataset_record: dict[str, Any] = {
            "id": group.dataset_id,
            "version": version,
            "sources": [registry.sources[key] for key in source_keys],
        }
        if group.collection == "extra":
            sample = ordered[0]
            dataset_record["repository"] = sample.repository_record
            dataset_record["collision_induced_absorption_xsecs"] = {
                **(sample.input_xsecs_metadata or {}),
                "min_temperature": min(temperatures),
                "max_temperature": max(temperatures),
                "min_wavenumber": actual_min,
                "max_wavenumber": actual_max,
                "column_schemas": sample.column_schemas,
                "default_column_schema": sample.default_column_schema,
                "files": file_entries,
            }
        else:
            dataset_record["repository"] = {
                "name": REPOSITORY_NAME,
                "version": versions[0] if len(versions) == 1 else versions,
                "collection": group.collection,
                "original_files": sorted(
                    {block.raw_relative_path for block in group.blocks}
                ),
            }
            dataset_record["collision_induced_absorption_xsecs"] = {
                "min_temperature": min(temperatures),
                "max_temperature": max(temperatures),
                "min_wavenumber": actual_min,
                "max_wavenumber": actual_max,
                "units": {
                    "temperature": "K",
                    "wavenumber_resolution": "cm-1",
                },
                "column_schemas": _column_schemas(
                    any(block.points[0].uncertainty is not None for block in ordered)
                ),
                "default_column_schema": "standard",
                "files": file_entries,
            }
        if variants:
            dataset_record["variants"] = variants
        dataset_json = {
            "collision_pair": _collision_pair(group, registry),
            "dataset": dataset_record,
        }
        _json_write(pair_dir / metadata_name, dataset_json)
        pair_groups[group.pair].append(
            {
                "dataset_id": group.dataset_id,
                "dataset_version": version,
                "metadata_file": metadata_name,
                "recommended": group.recommended,
                "collection": group.collection,
            }
        )

    for pair, entries in pair_groups.items():
        group = next(group for group in groups if group.pair == pair)
        ordered_entries = sorted(
            entries, key=lambda item: (not item["recommended"], item["dataset_id"])
        )
        recommended = [
            entry["dataset_id"] for entry in ordered_entries if entry["recommended"]
        ]
        pair_json = {
            "collision_pair": _collision_pair(group, registry),
            "version": version,
            "recommended_dataset": recommended[0] if recommended else None,
            "datasets": [
                {
                    "dataset_id": entry["dataset_id"],
                    "dataset_version": entry["dataset_version"],
                    "metadata_file": entry["metadata_file"],
                }
                for entry in ordered_entries
            ],
        }
        _json_write(output_dir / pair / f"{pair}.json", pair_json)

    write_master(output_dir, context)
    validation = validate_generated_release(
        output_dir, metadata_dir, groups, manifest, context, examples_dir
    )
    summary = {
        "schema_version": 1,
        "version": version,
        "build_date": context.build_date.isoformat(),
        "build_timezone": context.timezone,
        "output_root": "output",
        "pair_count": len(pair_groups),
        "dataset_count": len(groups),
        "metadata_json_count": len(groups),
        "pair_json_count": len(pair_groups),
        "master_json_count": 1,
        "cia_file_count": len(manifest),
        "two_column_cia_count": sum(
            item["block"].points[0].uncertainty is None for item in manifest
        ),
        "three_column_cia_count": sum(
            item["block"].points[0].uncertainty is not None for item in manifest
        ),
        "input_block_count": len(blocks),
        "hitran_raw_block_count": sum(block.input_kind == "hitran" for block in blocks),
        "extra_output_group_count": sum(block.input_kind == "extradata" for block in blocks),
        "extra_descriptor_count": len(
            {block.raw_relative_path for block in blocks if block.input_kind == "extradata"}
        ),
        "output_block_count": len(manifest),
        "deliberately_skipped_block_count": len(skipped_ids),
        "recommended_dataset_count": sum(group.recommended for group in groups),
        "supplementary_dataset_count": sum(not group.recommended for group in groups),
        "warnings_by_category": warning_audit["counts"],
        "warning_audit": warning_audit,
        "blocking_errors": warning_audit["blocking"],
        "missing_metadata": registry.problems,
        "unresolved_sources": sorted(
            {
                block.reference_number
                for block in blocks
                if not block.citation_keys
            }
        ),
        "unresolved_species": [
            problem
            for problem in registry.problems
            if "species" in problem.get("problem", "")
        ],
        "broken_references": validation["broken_references"],
        "filename_collisions": validation["filename_collisions"],
        "numeric_mismatches": validation["numeric_mismatches"],
        "master": {
            "path": MASTER_FILENAME,
            "id": "CIA.master",
            "pair_count": validation["master_validation"]["pair_count"],
            "recommended_pair_count": validation["master_validation"][
                "recommended_pair_count"
            ],
            "supplementary_only_pair_count": validation["master_validation"][
                "supplementary_only_pair_count"
            ],
            "null_recommended_pairs": validation["master_validation"][
                "null_recommended_pairs"
            ],
            "broken_pair_files": validation["master_validation"][
                "broken_pair_files"
            ],
            "broken_recommended_metadata": validation["master_validation"][
                "broken_recommended_metadata"
            ],
            "orphan_pair_json": validation["master_validation"][
                "orphan_pair_json"
            ],
            "orphan_dataset_json": validation["master_validation"][
                "orphan_dataset_json"
            ],
            "orphan_cia_files": validation["master_validation"][
                "orphan_cia_files"
            ],
            "cross_file_version_mismatches": validation["master_validation"][
                "cross_file_version_mismatches"
            ],
        },
        "strict_build_ready": not warning_audit["blocking"]
        and validation["summary"]["errors"] == 0
        and validation["master_validation"]["valid"],
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    _json_write(reports_dir / "final_build_summary.json", summary)
    _json_write(reports_dir / "final_validation.json", validation)
    return summary, validation, third_report


def validate_generated_release(
    output_dir: Path,
    metadata_dir: Path,
    groups: list[DatasetGroup],
    manifest: list[dict[str, Any]],
    context: BuildContext,
    examples_dir: Path | None = None,
) -> dict[str, Any]:
    version = context.version
    registry = load_metadata(metadata_dir, strict=False)
    errors: list[dict[str, Any]] = []
    broken: list[dict[str, Any]] = []
    numeric_mismatches: list[dict[str, Any]] = []
    filename_collisions: list[str] = []
    filename_metadata_mismatches: list[dict[str, Any]] = []
    expected_json: set[Path] = {output_dir / MASTER_FILENAME}
    expected_cia: set[Path] = set()
    group_index = {(group.pair, group.dataset_id): group for group in groups}
    cia_manifest = {
        (item["pair"], item["dataset_id"], item["cia_filename"]): item
        for item in manifest
    }
    seen_paths: Counter[Path] = Counter()

    for pair_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        pair = pair_dir.name
        pair_path = pair_dir / f"{pair}.json"
        expected_json.add(pair_path)
        if not pair_path.exists():
            broken.append({"pair": pair, "problem": "missing pair JSON"})
            continue
        pair_data = json.loads(pair_path.read_text())
        if pair_data.get("version") != version:
            errors.append({"file": str(pair_path), "problem": "version mismatch"})
        dataset_ids = [entry["dataset_id"] for entry in pair_data["datasets"]]
        duplicates = [item for item, count in Counter(dataset_ids).items() if count > 1]
        if duplicates:
            errors.append(
                {"file": str(pair_path), "problem": f"duplicate dataset IDs: {duplicates}"}
            )
        recommended = pair_data["recommended_dataset"]
        recommended_groups = [
            group for group in groups if group.pair == pair and group.recommended
        ]
        expected_recommended = (
            recommended_groups[0].dataset_id if recommended_groups else None
        )
        if recommended != expected_recommended:
            errors.append(
                {"file": str(pair_path), "problem": "recommended dataset mismatch"}
            )
        if recommended and not group_index[(pair, recommended)].recommended:
            errors.append(
                {"file": str(pair_path), "problem": "supplementary dataset is recommended"}
            )
        for entry in pair_data["datasets"]:
            dataset_path = pair_dir / entry["metadata_file"]
            expected_json.add(dataset_path)
            seen_paths[dataset_path] += 1
            if not dataset_path.exists():
                broken.append(
                    {"file": str(pair_path), "problem": f"missing {entry['metadata_file']}"}
                )
                continue
            data = json.loads(dataset_path.read_text())
            dataset = data["dataset"]
            if dataset["id"] != entry["dataset_id"]:
                broken.append(
                    {"file": str(dataset_path), "problem": "dataset.id linkage mismatch"}
                )
            expected_group = group_index[(pair, dataset["id"])]
            if expected_group.collection == "extra":
                if "recommendation_status" in dataset:
                    errors.append(
                        {"file": str(dataset_path), "problem": "output dataset must not duplicate pair recommendation status"}
                    )
                repository = dataset.get("repository")
                if repository != expected_group.blocks[0].repository_record:
                    errors.append(
                        {"file": str(dataset_path), "problem": "extra repository metadata mismatch"}
                    )
                elif repository.get("version") is not None:
                    errors.append(
                        {"file": str(dataset_path), "problem": "extra repository version must be null"}
                    )
                else:
                    project_root = expected_group.blocks[0].source_path.parents[3]
                    provenance = project_root / "source_data/non_hitran" / repository["collection"]
                    for original_file in repository.get("original_files", []):
                        if not isinstance(original_file, str) or "/" in original_file or "\\" in original_file or not (provenance / original_file).is_file():
                            errors.append(
                                {"file": str(dataset_path), "problem": f"extra repository original_file is missing or unsafe: {original_file!r}"}
                            )
            elif dataset.get("repository", {}).get("collection") != expected_group.collection:
                errors.append(
                    {"file": str(dataset_path), "problem": "collection mismatch"}
                )
            source_keys = [source["citation_key"] for source in dataset["sources"]]
            expected_source_keys = dataset_source_keys(expected_group)
            if source_keys != expected_source_keys:
                errors.append(
                    {
                        "file": str(dataset_path),
                        "problem": (
                            "dataset sources mismatch: expected "
                            f"{expected_source_keys!r}, got {source_keys!r}"
                        ),
                    }
                )
            if len(source_keys) != len(set(source_keys)):
                errors.append(
                    {"file": str(dataset_path), "problem": "duplicate dataset source IDs"}
                )
            for source_key in source_keys:
                if source_key not in registry.sources:
                    errors.append(
                        {"file": str(dataset_path), "problem": f"unknown source {source_key}"}
                    )
            for source in dataset["sources"]:
                source_key = source.get("citation_key")
                if source_key in registry.sources and source != registry.sources[source_key]:
                    errors.append(
                        {
                            "file": str(dataset_path),
                            "problem": f"embedded source record mismatch for {source_key}",
                        }
                    )
            for component in data["collision_pair"]["components"]:
                if component["slug"] not in registry.species:
                    errors.append(
                        {
                            "file": str(dataset_path),
                            "problem": f"unknown species {component['slug']}",
                        }
                    )
                if "cas_number" in component:
                    errors.append(
                        {"file": str(dataset_path), "problem": "forbidden cas_number field"}
                    )
            xsecs = dataset["collision_induced_absorption_xsecs"]
            schema_errors = _validate_column_schemas(xsecs, dataset_path)
            errors.extend(schema_errors)
            expected_metadata_name = dataset_metadata_filename(
                pair,
                dataset["id"],
                xsecs["min_wavenumber"],
                xsecs["max_wavenumber"],
                xsecs["min_temperature"],
                xsecs["max_temperature"],
            )
            if dataset_path.name != expected_metadata_name:
                filename_metadata_mismatches.append(
                    {
                        "file": str(dataset_path),
                        "expected": expected_metadata_name,
                        "problem": "metadata filename does not encode JSON ranges",
                    }
                )
            for file_entry in xsecs["files"]:
                cia_path = pair_dir / file_entry["filename"]
                expected_cia.add(cia_path)
                seen_paths[cia_path] += 1
                if not cia_path.exists():
                    broken.append(
                        {"file": str(dataset_path), "problem": f"missing {cia_path.name}"}
                    )
                    continue
                key = (pair, dataset["id"], cia_path.name)
                item = cia_manifest.get(key)
                if item is None:
                    broken.append(
                        {"file": str(cia_path), "problem": "no input-block manifest link"}
                    )
                    continue
                if item["metadata_filename"] != dataset_path.name:
                    filename_metadata_mismatches.append(
                        {
                            "file": str(cia_path),
                            "problem": "CIA manifest points to a different dataset metadata filename",
                        }
                    )
                _validate_numeric_file(
                    cia_path,
                    file_entry,
                    item["block"],
                    xsecs["column_schemas"],
                    xsecs["default_column_schema"],
                    numeric_mismatches,
                )
    filename_collisions.extend(
        str(path) for path, count in seen_paths.items() if count > 1
    )
    actual_json = set(output_dir.rglob("*.json"))
    actual_cia = set(output_dir.rglob("*.cia"))
    orphan_json = sorted(str(path) for path in actual_json - expected_json)
    orphan_cia = sorted(str(path) for path in actual_cia - expected_cia)
    if orphan_json:
        errors.append({"problem": "orphan dataset JSON", "files": orphan_json})
    if orphan_cia:
        errors.append({"problem": "orphan CIA file", "files": orphan_cia})
    errors.extend(broken)
    errors.extend(filename_metadata_mismatches)
    errors.extend(
        {"file": item["file"], "problem": item["problem"]}
        for item in numeric_mismatches
    )

    golden = validate_golden(output_dir, examples_dir)
    if not golden["passed"]:
        errors.append({"problem": "golden CO2-CH4 comparison failed", **golden})
    master_validation = validate_master(output_dir, context)
    if not master_validation["valid"]:
        errors.extend(master_validation["errors"])
    return {
        "schema_version": 1,
        "summary": {
            "errors": len(errors),
            "broken_references": len(broken),
            "filename_collisions": len(filename_collisions),
            "numeric_mismatches": len(numeric_mismatches),
            "orphan_dataset_json": len(orphan_json),
            "orphan_cia_files": len(orphan_cia),
            "filename_metadata_mismatches": len(filename_metadata_mismatches),
            "validated_cia_files": len(manifest),
            "master_errors": len(master_validation["errors"]),
        },
        "errors": errors,
        "broken_references": broken,
        "filename_collisions": filename_collisions,
        "numeric_mismatches": numeric_mismatches,
        "orphan_dataset_json": orphan_json,
        "orphan_cia_files": orphan_cia,
        "filename_metadata_mismatches": filename_metadata_mismatches,
        "golden_co2_ch4_100k": golden,
        "master_validation": master_validation,
    }


def _validate_numeric_file(
    path: Path,
    entry: dict[str, Any],
    block: CIABlock,
    column_schemas: dict[str, list[dict[str, Any]]],
    default_column_schema: str,
    mismatches: list[dict[str, Any]],
) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    expected_lines = [point.raw_line for point in block.points]
    problem: list[str] = []
    if len(lines) != len(expected_lines):
        problem.append("point count differs")
    if block.input_kind == "extradata" or (
        block.points and block.points[0].uncertainty is not None
    ):
        # Uncertainty-bearing files are rare and receive a complete raw-text check.
        positions = range(len(expected_lines))
    else:
        positions = sorted(
            {
                0,
                max(0, len(expected_lines) - 1),
                *(
                    int((len(expected_lines) - 1) * index / 6)
                    for index in range(1, 6)
                ),
            }
        )
    for index in positions:
        if index >= len(lines) or lines[index] != expected_lines[index]:
            problem.append(f"raw row mismatch at zero-based index {index}")
    effective_schema_name = entry.get(
        "column_schema", default_column_schema
    )
    effective_schema = column_schemas.get(effective_schema_name)
    expected_column_count = len(effective_schema or [])
    if expected_column_count < 2:
        problem.append("effective column schema must define at least 2 columns")
    input_column_count = (
        len(block.points[0].data_tokens)
        if block.input_kind == "extradata"
        else (3 if block.points and block.points[0].uncertainty is not None else 2)
    )
    if expected_column_count != input_column_count:
        problem.append("effective column schema does not match input column count")
    if block.input_kind == "hitran":
        expected_schema_name = (
            "with_absolute_uncertainty" if input_column_count == 3 else "standard"
        )
        if effective_schema_name != expected_schema_name:
            problem.append("effective column schema name is incorrect")
    parsed = []
    for line in lines:
        columns = line.split()
        if len(columns) != expected_column_count:
            problem.append("output column count differs from effective column schema")
            break
        try:
            values = tuple(float(value) for value in columns)
        except ValueError:
            problem.append("non-numeric output value")
            break
        if not all(math.isfinite(value) for value in values):
            problem.append("non-finite output value")
            break
        parsed.append(values)
        if effective_schema:
            names = [column.get("name") for column in effective_schema]
            if "uncertainty" in names and values[names.index("uncertainty")] < 0:
                problem.append("output uncertainty is negative")
                break
    if parsed and any(
        later[0] <= earlier[0] for earlier, later in zip(parsed, parsed[1:])
    ):
        problem.append("output wavenumbers are not strictly increasing")
    if entry["temperature"] != block.temperature:
        problem.append("temperature attribution mismatch")
    if block.input_kind == "hitran" and entry.get("reference_number") != block.reference_number:
        problem.append("reference attribution mismatch")
    if block.input_kind == "extradata" and "reference_number" in entry:
        problem.append("extradata file must not have a HITRAN reference number")
    if entry.get("variant") != block.variant:
        problem.append("variant attribution mismatch")
    if entry["citation_keys"] != list(block.citation_keys):
        problem.append("source attribution mismatch")
    if entry["npoints"] != len(block.points):
        problem.append("metadata point count mismatch")
    if entry["wavenumber_resolution"] != block.resolution:
        problem.append("source resolution metadata mismatch")
    if block.input_kind == "extradata":
        expected_regions = block.spectral_regions
        supplied_regions = entry.get("spectral_regions")
        if len(expected_regions) > 1:
            if supplied_regions is None:
                problem.append("spectral_regions is required when the file contains gaps")
            else:
                try:
                    validate_spectral_regions(tuple(supplied_regions), block.points)
                    if tuple(supplied_regions) != expected_regions:
                        problem.append("spectral_regions does not match detected gaps")
                except Exception as exc:
                    problem.append(f"spectral region validation failed: {exc}")
        elif supplied_regions is not None:
            problem.append("spectral_regions must be omitted for a continuous file")
    if problem:
        mismatches.append({"file": str(path), "problem": "; ".join(sorted(set(problem)))})


def _validate_column_schemas(
    xsecs: dict[str, Any], dataset_path: Path
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    schemas = xsecs.get("column_schemas")
    default_name = xsecs.get("default_column_schema")
    if not isinstance(schemas, dict):
        return [
            {
                "file": str(dataset_path),
                "problem": "column_schemas must be an object",
            }
        ]
    if default_name not in schemas:
        problems.append(
            {
                "file": str(dataset_path),
                "problem": "default_column_schema does not exist in column_schemas",
            }
        )
    if "standard" in schemas and schemas.get("standard") != STANDARD_COLUMN_SCHEMA:
        problems.append(
            {
                "file": str(dataset_path),
                "problem": "standard column schema must define the canonical two columns",
            }
        )
    if "with_absolute_uncertainty" in schemas:
        uncertainty_schema = schemas["with_absolute_uncertainty"]
        if "standard" in schemas and uncertainty_schema != ABSOLUTE_UNCERTAINTY_COLUMN_SCHEMA:
            problems.append(
                {
                    "file": str(dataset_path),
                    "problem": "HITRAN with_absolute_uncertainty schema is invalid",
                }
            )
        elif isinstance(uncertainty_schema, list) and uncertainty_schema:
            names = [column["name"] for column in uncertainty_schema]
            uncertainty = uncertainty_schema[-1]
            coefficient = next(
                (column for column in uncertainty_schema if column.get("name") == "cia_coefficient"),
                None,
            )
            if coefficient is None or uncertainty.get("units") != coefficient.get("units"):
                problems.append(
                    {
                        "file": str(dataset_path),
                        "problem": "uncertainty units differ from cia_coefficient units",
                    }
                )
    for schema_name, schema in schemas.items():
        if not isinstance(schema, list) or len(schema) < 2:
            problems.append(
                {"file": str(dataset_path), "problem": f"column schema {schema_name!r} is invalid"}
            )
            continue
        names = [column.get("name") for column in schema if isinstance(column, dict)]
        if len(names) != len(schema) or "wavenumber" not in names or len(names) != len(set(names)):
            problems.append(
                {"file": str(dataset_path), "problem": f"column schema {schema_name!r} has invalid columns"}
            )
        for column in schema:
            if column.get("name") == "uncertainty":
                applies_to = column.get("applies_to")
                if column.get("uncertainty_type") != "absolute" or applies_to not in names:
                    problems.append(
                        {"file": str(dataset_path), "problem": f"column schema {schema_name!r} has invalid uncertainty metadata"}
                    )
                else:
                    target = next(item for item in schema if item.get("name") == applies_to)
                    if target.get("units") != column.get("units"):
                        problems.append(
                            {"file": str(dataset_path), "problem": "uncertainty units differ from applies_to units"}
                        )
    used = {default_name}
    for file_entry in xsecs.get("files", []):
        schema_name = file_entry.get("column_schema", default_name)
        used.add(schema_name)
        if schema_name not in schemas:
            problems.append(
                {
                    "file": str(dataset_path),
                    "problem": f"file references unknown column schema {schema_name!r}",
                }
            )
        if "data_columns" in file_entry:
            problems.append(
                {
                    "file": str(dataset_path),
                    "problem": "file-level data_columns are not allowed",
                }
            )
    unused = sorted(set(schemas) - used)
    if unused:
        problems.append(
            {
                "file": str(dataset_path),
                "problem": f"unused column schemas: {unused}",
            }
        )
    return problems


def validate_golden(
    output_dir: Path, examples_dir: Path | None = None
) -> dict[str, Any]:
    generated = (
        output_dir
        / "CO2-CH4"
        / "CO2-CH4_fakhardji2022_0_720_100.cia"
    )
    example = (
        examples_dir / "CO2-CH4_fakhardji2022_0_720_100.cia"
        if examples_dir is not None
        else output_dir.parent / "examples" / "CO2-CH4_fakhardji2022_0_720_100.cia"
    )
    if not generated.exists() or not example.exists():
        return {
            "passed": False,
            "problem": "generated or example golden file is missing",
        }
    generated_lines = generated.read_text().splitlines()
    example_lines = example.read_text().splitlines()
    numeric_equal = len(generated_lines) == len(example_lines) and all(
        left.split() == right.split()
        for left, right in zip(generated_lines, example_lines)
    )
    return {
        "passed": numeric_equal,
        "comparison": "complete line-by-line token comparison",
        "generated_rows": len(generated_lines),
        "example_rows": len(example_lines),
        "first_wavenumber": generated_lines[0].split()[0] if generated_lines else None,
        "last_wavenumber": generated_lines[-1].split()[0] if generated_lines else None,
        "exact_text_match": generated_lines == example_lines,
    }

