from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class ChandranConversionError(ValueError):
    """Raised when the archived Chandran & Karman data are incomplete or invalid."""


@dataclass(frozen=True)
class SourceSpec:
    prefix: str
    header_pair: str
    canonical_pair: str
    components: tuple[str, str]
    temperatures: tuple[int, ...]
    npoints: int
    maximum: int


SPECS = (
    SourceSpec("HeAr", "Ar-He", "Ar-He", ("ar", "he"), (165, 295, 1000, 2000), 600, 3000),
    SourceSpec("NeAr", "Ne-Ar", "Ar-Ne", ("ar", "ne"), (165, 295, 1000, 2000), 600, 3000),
    SourceSpec("HeNe", "Ne-He", "He-Ne", ("he", "ne"), (77, 1000, 2000), 800, 4000),
)
HEADER = re.compile(r"^//Data for CIA of (?P<pair>\S+) at (?P<temperature>\d+) K$")


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_files() -> dict[str, tuple[SourceSpec, int]]:
    """Return the complete, deterministic source-file contract."""
    return {
        f"CIA_{spec.prefix}_{temperature}K.data": (spec, temperature)
        for spec in SPECS
        for temperature in spec.temperatures
    }


def _number(token: str, path: Path, line_number: int) -> Decimal:
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise ChandranConversionError(f"{path}:{line_number}: invalid number {token!r}") from exc
    if not value.is_finite():
        raise ChandranConversionError(f"{path}:{line_number}: non-finite number {token!r}")
    return value


def parse_source(path: Path, spec: SourceSpec, temperature: int) -> list[tuple[str, str, str]]:
    """Parse and validate one three-column archived source file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ChandranConversionError(f"{path}: empty source file")
    match = HEADER.fullmatch(lines[0])
    if not match or match.group("pair") != spec.header_pair:
        raise ChandranConversionError(f"{path}: header pair does not match {spec.header_pair}")
    if int(match.group("temperature")) != temperature:
        raise ChandranConversionError(f"{path}: filename/header temperature mismatch")
    rows: list[tuple[str, str, str]] = []
    previous: Decimal | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        tokens = stripped.split()
        if len(tokens) != 3:
            raise ChandranConversionError(f"{path}:{line_number}: expected 3 columns, found {len(tokens)}")
        wavenumber, coefficient, uncertainty = (
            _number(token, path, line_number) for token in tokens
        )
        if coefficient < 0 or uncertainty < 0:
            raise ChandranConversionError(f"{path}:{line_number}: coefficient/uncertainty is negative")
        if previous is not None:
            if wavenumber <= previous:
                raise ChandranConversionError(f"{path}:{line_number}: duplicate or non-monotonic wavenumber")
            if not math.isclose(float(wavenumber - previous), 5.0, rel_tol=0.0, abs_tol=1e-9):
                raise ChandranConversionError(f"{path}:{line_number}: grid step is not nominally 5 cm^-1")
        previous = wavenumber
        rows.append(tuple(tokens))
    if len(rows) != spec.npoints:
        raise ChandranConversionError(f"{path}: {len(rows)} points != {spec.npoints}")
    if Decimal(rows[0][0]) != 5 or Decimal(rows[-1][0]) != spec.maximum:
        raise ChandranConversionError(f"{path}: unexpected wavenumber range")
    return rows


def _descriptor(spec: SourceSpec, species: dict[str, dict[str, Any]]) -> dict[str, Any]:
    components = []
    for slug in spec.components:
        record = species[slug]
        components.append({
            "formula": record["formula"],
            "slug": record["slug"],
            "cas_registry_number": record["cas_registry_number"],
        })
    originals = [
        f"CIA_{spec.prefix}_{temperature}K.data" for temperature in spec.temperatures
    ]
    return {
        "collision_pair": {
            "formula": spec.canonical_pair,
            "slug": spec.canonical_pair.lower(),
            "active_species_status": "no_unique_active_species",
            "active_species": None,
            "collider": None,
            "components": components,
        },
        "dataset": {
            "id": "chandran2025",
            "recommendation_status": "supplementary",
            "repository": {
                "name": "JQSRT supplementary material",
                "version": None,
                "collection": "chandran2025",
                "original_files": originals,
            },
            "collision_induced_absorption_xsecs": {
                "min_temperature": min(spec.temperatures),
                "max_temperature": max(spec.temperatures),
                "min_wavenumber": 5,
                "max_wavenumber": spec.maximum,
                "nominal_wavenumber_step": 5,
                "units": {
                    "temperature": "K",
                    "wavenumber": "cm^-1",
                    "nominal_wavenumber_step": "cm^-1",
                },
                "column_schemas": {
                    "with_absolute_uncertainty": [
                        {"name": "wavenumber", "units": "cm^-1"},
                        {"name": "cia_coefficient", "units": "cm^-1 amagat^-2"},
                        {
                            "name": "uncertainty",
                            "units": "cm^-1 amagat^-2",
                            "uncertainty_type": "absolute",
                            "applies_to": "cia_coefficient",
                        },
                    ]
                },
                "default_column_schema": "with_absolute_uncertainty",
                "data_file": f"{spec.canonical_pair}.csv",
            },
            "sources": ["chandran2025"],
        },
    }


def convert(source_dir: Path, output_dir: Path, metadata_dir: Path) -> dict[str, Any]:
    """Convert the exact archived collection into three canonical CSV/JSON pairs."""
    contract = expected_files()
    actual = {path.name for path in source_dir.glob("*.data")}
    missing, unexpected = sorted(set(contract) - actual), sorted(actual - set(contract))
    if missing or unexpected:
        raise ChandranConversionError(
            f"source collection mismatch; missing={missing}, unexpected={unexpected}"
        )
    species = json.loads((metadata_dir / "species.json").read_text(encoding="utf-8"))
    sources = json.loads((metadata_dir / "sources.json").read_text(encoding="utf-8"))
    source = sources.get("chandran2025")
    if not source or source.get("verified") is not True or source.get("ref") is not None:
        raise ChandranConversionError("chandran2025 must be a verified null-ref source")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    parsed: dict[str, dict[int, list[tuple[str, str, str]]]] = {
        spec.canonical_pair: {} for spec in SPECS
    }
    for filename, (spec, temperature) in sorted(contract.items()):
        path = source_dir / filename
        rows = parse_source(path, spec, temperature)
        parsed[spec.canonical_pair][temperature] = rows
        manifests.append({
            "relative_path": f"source_data/non_hitran/chandran2025/{filename}",
            "byte_size": path.stat().st_size,
            "sha256": sha256(path),
        })
    outputs = []
    for spec in SPECS:
        csv_path = output_dir / f"{spec.canonical_pair}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["temperature", "wavenumber", "cia_coefficient", "uncertainty"])
            for temperature in sorted(parsed[spec.canonical_pair]):
                for row in parsed[spec.canonical_pair][temperature]:
                    writer.writerow([str(temperature), *row])
        json_path = output_dir / f"{spec.canonical_pair}.json"
        json_path.write_text(
            json.dumps(_descriptor(spec, species), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs.extend([
            {"path": csv_path.name, "byte_size": csv_path.stat().st_size, "sha256": sha256(csv_path)},
            {"path": json_path.name, "byte_size": json_path.stat().st_size, "sha256": sha256(json_path)},
        ])
    return {
        "source_file_count": len(manifests),
        "source_files": manifests,
        "pair_count": len(SPECS),
        "temperature_group_count": sum(len(value) for value in parsed.values()),
        "data_row_count": sum(len(rows) for value in parsed.values() for rows in value.values()),
        "pairs": {
            spec.canonical_pair: {
                str(t): {"npoints": len(parsed[spec.canonical_pair][t]), "min_wavenumber": parsed[spec.canonical_pair][t][0][0], "max_wavenumber": parsed[spec.canonical_pair][t][-1][0]}
                for t in sorted(parsed[spec.canonical_pair])
            }
            for spec in SPECS
        },
        "outputs": outputs,
        "validation_result": "passed",
    }
