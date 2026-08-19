from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class DongConversionError(ValueError):
    """Raised when the archived Dong 2026 source is malformed."""


SOURCE_NAME = "CIA B_O2-O2_1.06um.txt"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(token: str, path: Path, line: int) -> Decimal:
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise DongConversionError(f"{path}:{line}: invalid number {token!r}") from exc
    if not value.is_finite():
        raise DongConversionError(f"{path}:{line}: non-finite number {token!r}")
    return value


def parse_source(path: Path) -> list[tuple[str, str, str]]:
    """Parse the whitespace-delimited Dong source while preserving tokens."""
    lines = path.read_text(encoding="utf-8").splitlines()
    expected = (
        "O2-O2 Collision-Induced Absorption (CIA) Data in the 1.06 μm Band at 296 K",
        "Wavenumber    Binary CIA coefficient    Uncertainty",
        "cm^-1         cm^-1 amagat^-2           cm^-1 amagat^-2",
    )
    nonempty = [line for line in lines if line.strip()]
    if len(nonempty) < 4 or nonempty[:3] != list(expected):
        raise DongConversionError(f"{path}: header/pair/temperature/units mismatch")
    rows: list[tuple[str, str, str]] = []
    previous: Decimal | None = None
    for line_number, line in enumerate(lines, start=1):
        if line_number <= 4:
            continue
        tokens = line.split()
        if not tokens:
            continue
        if len(tokens) != 3:
            raise DongConversionError(f"{path}:{line_number}: expected 3 columns, found {len(tokens)}")
        wavenumber, coefficient, uncertainty = (_number(x, path, line_number) for x in tokens)
        if coefficient < 0 or uncertainty < 0:
            raise DongConversionError(f"{path}:{line_number}: coefficient/uncertainty is negative")
        if previous is not None:
            if wavenumber <= previous:
                raise DongConversionError(f"{path}:{line_number}: duplicate/non-monotonic wavenumber")
            if abs((wavenumber - previous) - Decimal("0.01")) > Decimal("1e-12"):
                raise DongConversionError(f"{path}:{line_number}: grid step is not 0.01 cm^-1")
        previous = wavenumber
        rows.append(tuple(tokens))
    if len(rows) != 70001 or Decimal(rows[0][0]) != 9120 or Decimal(rows[-1][0]) != 9820:
        raise DongConversionError(f"{path}: expected 70001 points spanning 9120..9820")
    return rows


def _component(species: dict[str, dict[str, Any]], slug: str) -> dict[str, Any]:
    value = species[slug]
    return {key: value[key] for key in ("formula", "slug", "cas_registry_number")}


def descriptor(species: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the canonical Dong extra descriptor."""
    return {
        "collision_pair": {
            "formula": "O2-O2", "slug": "o2-o2",
            "active_species_status": "unique", "active_species": "o2", "collider": "o2",
            "components": [_component(species, "o2"), _component(species, "o2")],
        },
        "dataset": {
            "id": "dong2026", "recommendation_status": "supplementary",
            "repository": {
                "name": "JQSRT supplementary material", "version": None,
                "collection": "dong2026", "original_files": [SOURCE_NAME],
            },
            "collision_induced_absorption_xsecs": {
                "min_temperature": 296, "max_temperature": 296,
                "min_wavenumber": 9120, "max_wavenumber": 9820,
                "wavenumber_resolution": None, "nominal_wavenumber_step": 0.01,
                "units": {"temperature": "K", "wavenumber": "cm^-1", "wavenumber_resolution": "cm^-1", "nominal_wavenumber_step": "cm^-1"},
                "column_schemas": {"with_absolute_uncertainty": [
                    {"name": "wavenumber", "units": "cm^-1"},
                    {"name": "cia_coefficient", "units": "cm^-1 amagat^-2"},
                    {"name": "uncertainty", "units": "cm^-1 amagat^-2", "uncertainty_type": "absolute", "applies_to": "cia_coefficient", "uncertainty_level": "1_sigma", "description": "combined standard uncertainty, 1 sigma"},
                ]},
                "default_column_schema": "with_absolute_uncertainty", "data_file": "O2-O2.csv",
            },
            "sources": ["dong2026"],
        },
    }


def convert(source_dir: Path, output_dir: Path, metadata_dir: Path) -> dict[str, Any]:
    """Convert the exact Dong archive to deterministic canonical inputs."""
    actual = {path.name for path in source_dir.iterdir() if path.is_file()} if source_dir.is_dir() else set()
    if actual != {SOURCE_NAME}:
        missing = sorted({SOURCE_NAME} - actual)
        unexpected = sorted(actual - {SOURCE_NAME})
        raise DongConversionError(
            f"source collection mismatch; missing={missing}, unexpected={unexpected}"
        )
    source = source_dir / SOURCE_NAME
    rows = parse_source(source)
    species = json.loads((metadata_dir / "species.json").read_text(encoding="utf-8"))
    bibliography = json.loads((metadata_dir / "sources.json").read_text(encoding="utf-8"))["dong2026"]
    if bibliography.get("verified") is not True or bibliography.get("ref") is not None:
        raise DongConversionError("dong2026 must be a verified null-ref source")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "O2-O2.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["temperature", "wavenumber", "cia_coefficient", "uncertainty"])
        writer.writerows(("296", *row) for row in rows)
    json_path = output_dir / "O2-O2.json"
    json_path.write_text(json.dumps(descriptor(species), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source_files": [{"relative_path": f"source_data/non_hitran/dong2026/{SOURCE_NAME}", "byte_size": source.stat().st_size, "sha256": _sha(source)}],
        "data_row_count": len(rows), "temperature_group_count": 1,
        "outputs": [{"path": x.name, "byte_size": x.stat().st_size, "sha256": _sha(x)} for x in (csv_path, json_path)],
        "validation_result": "passed",
    }
