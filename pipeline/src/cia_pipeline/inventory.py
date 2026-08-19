"""check all inputs before all"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .grouping import assign_proposed_groups
from .hitran_parser import parse_file, parse_repository_version
from .metadata import load_metadata
from .models import CIABlock, CIAParseError


def _mapped_path(input_dir: Path, relative: str) -> Path:
    return input_dir / Path(relative)


def create_inventory(
    input_dir: Path, metadata_dir: Path, strict: bool = False
) -> tuple[dict[str, Any], bool]:
    registry = load_metadata(metadata_dir, strict=strict)
    blocks: list[CIABlock] = []
    issues: list[dict[str, Any]] = list(registry.problems)
    disk_files = {
        path.relative_to(input_dir).as_posix()
        for path in input_dir.rglob("*.cia.txt")
        if path.is_file()
    }
    mapped_files = {
        path for path in registry.dataset_files if path.startswith(("main/", "sup/"))
    }
    for relative in sorted(disk_files - mapped_files):
        issues.append({"raw_relative_path": relative, "problem": "unmapped raw file"})
    for relative in sorted(mapped_files - disk_files):
        issues.append({"raw_relative_path": relative, "problem": "mapped raw file is missing"})

    for relative in sorted(mapped_files & disk_files):
        entry = registry.dataset_files[relative]
        path = _mapped_path(input_dir, relative)
        try:
            parsed = parse_file(path, raw_relative_path=relative)
            repository_version = parse_repository_version(path.name)
        except (CIAParseError, ValueError) as exc:
            issues.append({"raw_relative_path": relative, "problem": str(exc)})
            continue
        for block in parsed:
            block.collection = relative.split("/", 1)[0]
            block.repository_version = repository_version
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
            if not block.citation_keys:
                block.warnings.append(
                    f"unresolved HITRAN reference {block.reference_number}"
                )
                issues.append(
                    {
                        "raw_relative_path": relative,
                        "header_line_number": block.header_line_number,
                        "problem": f"unknown reference number {block.reference_number}",
                    }
                )
            for warning in block.warnings:
                if warning.startswith("non-monotonic"):
                    issues.append(
                        {
                            "raw_relative_path": relative,
                            "header_line_number": block.header_line_number,
                            "problem": warning,
                        }
                    )
            blocks.append(block)

    ambiguities = assign_proposed_groups(blocks)
    issues.extend({"problem": item, "category": "grouping_ambiguity"} for item in ambiguities)
    counts = Counter(block.collection for block in blocks)
    unresolved = sorted(
        {
            block.reference_number
            for block in blocks
            if not block.citation_keys
        }
    )
    report = {
        "schema_version": 1,
        "input_root": str(input_dir.resolve()),
        "metadata_root": str(metadata_dir.resolve()),
        "summary": {
            "raw_files_on_disk": len(disk_files),
            "mapped_files": len(mapped_files),
            "parsed_files": len({block.raw_relative_path for block in blocks}),
            "blocks": len(blocks),
            "blocks_by_collection": dict(sorted(counts.items())),
            "resolved_blocks": sum(bool(block.citation_keys) for block in blocks),
            "unresolved_blocks": sum(not block.citation_keys for block in blocks),
            "unresolved_reference_numbers": unresolved,
            "metadata_problems": len(registry.problems),
            "grouping_ambiguities": len(ambiguities),
            "issues": len(issues),
        },
        "metadata_validation": {
            "species_records": len(registry.species),
            "source_records": len(registry.sources),
            "reference_numbers": len(registry.references),
            "duplicate_reference_numbers": {
                str(ref): list(keys)
                for ref, keys in registry.references.items()
                if len(keys) > 1
            },
            "problems": registry.problems,
        },
        "grouping_ambiguities": ambiguities,
        "issues": issues,
        "blocks": [block.inventory_dict() for block in blocks],
    }
    failed = bool(issues) if strict else False
    return report, failed


def readable_summary(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "HITRAN CIA inventory",
        "====================",
        f"Input root: {report['input_root']}",
        f"Metadata root: {report['metadata_root']}",
        "",
        f"Raw files on disk: {summary['raw_files_on_disk']}",
        f"Mapped files: {summary['mapped_files']}",
        f"Parsed files: {summary['parsed_files']}",
        f"Blocks: {summary['blocks']}",
        f"  main: {summary['blocks_by_collection'].get('main', 0)}",
        f"  sup: {summary['blocks_by_collection'].get('sup', 0)}",
        f"Resolved blocks: {summary['resolved_blocks']}",
        f"Unresolved blocks: {summary['unresolved_blocks']}",
        f"Metadata problems: {summary['metadata_problems']}",
        f"Grouping ambiguities: {summary['grouping_ambiguities']}",
        "",
        "Unresolved reference numbers: "
        + (
            ", ".join(map(str, summary["unresolved_reference_numbers"]))
            if summary["unresolved_reference_numbers"]
            else "none"
        ),
        "",
        "Grouping ambiguities:",
    ]
    lines.extend(f"- {item}" for item in report["grouping_ambiguities"])
    if not report["grouping_ambiguities"]:
        lines.append("- none")
    lines.extend(["", "Issues:"])
    for issue in report["issues"]:
        location = issue.get("raw_relative_path", "metadata/grouping")
        if issue.get("header_line_number"):
            location += f":{issue['header_line_number']}"
        lines.append(f"- {location}: {issue['problem']}")
    if not report["issues"]:
        lines.append("- none")
    lines.extend(["", "Proposed datasets:"])
    datasets: dict[str, set[str]] = {}
    for block in report["blocks"]:
        datasets.setdefault(block["proposed_dataset_id"], set()).add(
            block["normalized_pair"]
        )
    for dataset_id in sorted(datasets):
        lines.append(
            f"- {dataset_id}: {', '.join(sorted(datasets[dataset_id]))}"
        )
    return "\n".join(lines) + "\n"


def write_inventory(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
