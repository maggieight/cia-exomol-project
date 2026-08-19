from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def validate_ptashnik(output_root: Path, input_root: Path) -> dict[str, Any]:
    """Compare every Ptashnik CSV token with the generated CIA files."""
    pair_path = output_root / "H2O-H2O" / "H2O-H2O.json"
    pair = json.loads(pair_path.read_text(encoding="utf-8"))
    link = next(item for item in pair["datasets"] if item["dataset_id"] == "ptashnik2011")
    metadata = json.loads(
        (pair_path.parent / link["metadata_file"]).read_text(encoding="utf-8")
    )
    files = metadata["dataset"]["collision_induced_absorption_xsecs"]["files"]
    groups: dict[str, list[tuple[str, str, str]]] = {}
    csv_path = input_root / "extra/ptashnik2011/H2O-H2O.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            groups.setdefault(row["temperature"], []).append(
                (
                    row["wavenumber"],
                    row["self_continuum_cross_section"],
                    row["uncertainty"],
                )
            )
    mismatches: list[dict[str, Any]] = []
    matched_rows = 0
    results = []
    for entry in files:
        temperature = str(
            int(entry["temperature"])
            if float(entry["temperature"]).is_integer()
            else entry["temperature"]
        )
        expected = groups.get(temperature, [])
        actual = [
            tuple(line.split())
            for line in (pair_path.parent / entry["filename"]).read_text().splitlines()
        ]
        equal = actual == expected
        if equal:
            matched_rows += len(actual)
        else:
            mismatches.append(
                {
                    "filename": entry["filename"],
                    "problem": "complete token comparison failed",
                }
            )
        results.append(
            {
                "temperature": entry["temperature"],
                "filename": entry["filename"],
                "npoints": len(actual),
                "min_wavenumber": float(actual[0][0]),
                "max_wavenumber": float(actual[-1][0]),
                "complete_token_match": equal,
            }
        )
    return {
        "dataset_id": "ptashnik2011",
        "file_count": len(files),
        "matched_rows": matched_rows,
        "token_mismatches": len(mismatches),
        "mismatches": mismatches,
        "files": results,
        "pair_recommended_dataset": pair["recommended_dataset"],
        "validation_result": (
            "passed"
            if len(files) == 6 and matched_rows == 2771 and not mismatches
            else "failed"
        ),
    }


def validate_extra_collection(
    output_root: Path, input_root: Path, dataset_id: str
) -> dict[str, Any]:
    """Compare every canonical extra CSV token with generated CIA files."""
    descriptors = sorted((input_root / "extra" / dataset_id).glob("*.json"))
    results: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    matched_rows = 0
    for descriptor_path in descriptors:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        pair_name = descriptor["collision_pair"]["formula"]
        xsecs = descriptor["dataset"]["collision_induced_absorption_xsecs"]
        schema = xsecs["column_schemas"][xsecs["default_column_schema"]]
        names = [column["name"] for column in schema]
        groups: dict[tuple[str | None, str], list[tuple[str, ...]]] = {}
        with (descriptor_path.parent / xsecs["data_file"]).open(
            encoding="utf-8", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                key = (row.get("variant"), row["temperature"])
                groups.setdefault(key, []).append(tuple(row[name] for name in names))
        pair_path = output_root / pair_name / f"{pair_name}.json"
        pair = json.loads(pair_path.read_text(encoding="utf-8"))
        link = next(item for item in pair["datasets"] if item["dataset_id"] == dataset_id)
        metadata = json.loads(
            (pair_path.parent / link["metadata_file"]).read_text(encoding="utf-8")
        )
        files = metadata["dataset"]["collision_induced_absorption_xsecs"]["files"]
        for entry in files:
            temperature = str(
                int(entry["temperature"])
                if float(entry["temperature"]).is_integer()
                else entry["temperature"]
            )
            expected = groups.get((entry.get("variant"), temperature), [])
            actual = [
                tuple(line.split())
                for line in (pair_path.parent / entry["filename"]).read_text().splitlines()
            ]
            equal = actual == expected
            if equal:
                matched_rows += len(actual)
            else:
                mismatches.append(
                    {
                        "filename": entry["filename"],
                        "problem": "complete token comparison failed",
                    }
                )
            results.append(
                {
                    "pair": pair_name,
                    "temperature": entry["temperature"],
                    "variant": entry.get("variant"),
                    "filename": entry["filename"],
                    "npoints": len(actual),
                    "min_wavenumber": actual[0][0],
                    "max_wavenumber": actual[-1][0],
                    "complete_token_match": equal,
                }
            )
    return {
        "dataset_id": dataset_id,
        "descriptor_count": len(descriptors),
        "file_count": len(results),
        "matched_rows": matched_rows,
        "token_mismatches": len(mismatches),
        "numeric_mismatches": len(mismatches),
        "mismatches": mismatches,
        "files": results,
        "validation_result": "passed" if descriptors and not mismatches else "failed",
    }
