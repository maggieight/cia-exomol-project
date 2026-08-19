from __future__ import annotations

import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class VitaliConversionError(ValueError):
    """Raised when the archived Vitali 2026 source collection is malformed."""


TEMPERATURES = (241, 294, 349, 399, 451, 498)
EXPECTED = {
    241: (1320, ((3193, 3284, 92), (3906, 4769, 864), (5599, 5962, 364))),
    294: (1277, ((3193, 3284, 92), (3949, 4769, 821), (5599, 5962, 364))),
    349: (1277, ((3193, 3284, 92), (3949, 4769, 821), (5599, 5962, 364))),
    399: (1249, ((3193, 3284, 92), (3977, 4769, 793), (5599, 5962, 364))),
    451: (1230, ((3193, 3284, 92), (3996, 4769, 774), (5599, 5962, 364))),
    498: (1230, ((3193, 3284, 92), (3996, 4769, 774), (5599, 5962, 364))),
}
HEADER = re.compile(r"^Wavenumber \[cm\^-1\],BACs \[cm\^5 molecule\^-2\] T = (\d+) K,Sistematic errors \[cm\^5 molecule\^-2\]$")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(token: str, path: Path, line: int) -> Decimal:
    try:
        value = Decimal(token)
    except InvalidOperation as exc:
        raise VitaliConversionError(f"{path}:{line}: invalid number {token!r}") from exc
    if not value.is_finite():
        raise VitaliConversionError(f"{path}:{line}: non-finite number {token!r}")
    return value


def _regions(rows: list[tuple[str, str, str]]) -> tuple[tuple[int, int, int], ...]:
    groups: list[list[int]] = [[]]
    for row in rows:
        value = int(Decimal(row[0]))
        if groups[-1] and value != groups[-1][-1] + 1:
            groups.append([])
        groups[-1].append(value)
    return tuple((group[0], group[-1], len(group)) for group in groups)


def parse_source(path: Path, temperature: int) -> list[tuple[str, str, str]]:
    """Parse one comma-delimited Vitali source while preserving data tokens."""
    lines = path.read_text(encoding="utf-8").splitlines()
    match = HEADER.fullmatch(lines[0]) if lines else None
    if not match or int(match.group(1)) != temperature:
        raise VitaliConversionError(f"{path}: header/filename temperature or units mismatch")
    rows: list[tuple[str, str, str]] = []
    previous: Decimal | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        tokens = line.split(",")
        if len(tokens) != 3 or any(token == "" for token in tokens):
            raise VitaliConversionError(f"{path}:{line_number}: expected 3 comma-delimited columns")
        wavenumber, coefficient, uncertainty = (_number(x, path, line_number) for x in tokens)
        if coefficient < 0 or uncertainty < 0:
            raise VitaliConversionError(f"{path}:{line_number}: coefficient/uncertainty is negative")
        if previous is not None and wavenumber <= previous:
            raise VitaliConversionError(f"{path}:{line_number}: duplicate/non-monotonic wavenumber")
        previous = wavenumber
        rows.append(tuple(tokens))
    count, regions = EXPECTED[temperature]
    if len(rows) != count or _regions(rows) != regions:
        raise VitaliConversionError(f"{path}: point count or spectral regions differ from expected")
    return rows


def _component(species: dict[str, dict[str, Any]], slug: str) -> dict[str, Any]:
    value = species[slug]
    return {key: value[key] for key in ("formula", "slug", "cas_registry_number")}


def descriptor(species: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the canonical Vitali extra descriptor."""
    originals = [f"BAC_CIA_CO2_H2_{temperature}K.txt" for temperature in TEMPERATURES]
    return {
        "collision_pair": {
            "formula": "CO2-H2", "slug": "co2-h2", "active_species_status": "unique",
            "active_species": "co2", "collider": "h2",
            "components": [_component(species, "co2"), _component(species, "h2")],
        },
        "dataset": {
            "id": "vitali2026", "recommendation_status": "supplementary",
            "repository": {"name": "Icarus supplementary material", "version": None, "collection": "vitali2026", "original_files": originals},
            "collision_induced_absorption_xsecs": {
                "min_temperature": 241, "max_temperature": 498,
                "min_wavenumber": 3193, "max_wavenumber": 5962,
                "wavenumber_resolution": 1, "nominal_wavenumber_step": 1,
                "units": {"temperature": "K", "wavenumber": "cm^-1", "wavenumber_resolution": "cm^-1", "nominal_wavenumber_step": "cm^-1"},
                "column_schemas": {"with_systematic_absolute_uncertainty": [
                    {"name": "wavenumber", "units": "cm^-1"},
                    {"name": "cia_coefficient", "units": "cm^5 molecule^-2"},
                    {"name": "uncertainty", "units": "cm^5 molecule^-2", "uncertainty_type": "absolute", "uncertainty_category": "systematic", "applies_to": "cia_coefficient"},
                ]},
                "default_column_schema": "with_systematic_absolute_uncertainty", "data_file": "CO2-H2.csv",
            },
            "sources": ["vitali2026"],
        },
    }


def convert(source_dir: Path, output_dir: Path, metadata_dir: Path) -> dict[str, Any]:
    """Convert the exact Vitali archive to deterministic canonical inputs."""
    expected_names = {f"BAC_CIA_CO2_H2_{temperature}K.txt" for temperature in TEMPERATURES}
    actual = {path.name for path in source_dir.iterdir() if path.is_file()} if source_dir.is_dir() else set()
    if actual != expected_names:
        missing = sorted(expected_names - actual)
        unexpected = sorted(actual - expected_names)
        raise VitaliConversionError(
            f"source collection mismatch; missing={missing}, unexpected={unexpected}"
        )
    rows_by_temperature = {temperature: parse_source(source_dir / f"BAC_CIA_CO2_H2_{temperature}K.txt", temperature) for temperature in TEMPERATURES}
    species = json.loads((metadata_dir / "species.json").read_text(encoding="utf-8"))
    bibliography = json.loads((metadata_dir / "sources.json").read_text(encoding="utf-8"))["vitali2026"]
    if bibliography.get("verified") is not True or bibliography.get("ref") is not None:
        raise VitaliConversionError("vitali2026 must be a verified null-ref source")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "CO2-H2.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["temperature", "wavenumber", "cia_coefficient", "uncertainty"])
        for temperature in TEMPERATURES:
            writer.writerows((str(temperature), *row) for row in rows_by_temperature[temperature])
    json_path = output_dir / "CO2-H2.json"
    json_path.write_text(json.dumps(descriptor(species), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = [source_dir / name for name in sorted(expected_names)]
    return {
        "source_files": [{"relative_path": f"source_data/non_hitran/vitali2026/{x.name}", "byte_size": x.stat().st_size, "sha256": _sha(x)} for x in sources],
        "data_row_count": sum(map(len, rows_by_temperature.values())), "temperature_group_count": len(TEMPERATURES),
        "regions": {str(t): [list(x) for x in _regions(rows_by_temperature[t])] for t in TEMPERATURES},
        "outputs": [{"path": x.name, "byte_size": x.stat().st_size, "sha256": _sha(x)} for x in (csv_path, json_path)],
        "validation_result": "passed",
    }
