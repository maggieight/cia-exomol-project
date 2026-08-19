from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .hitran_parser import parse_file
from .models import CIABlock


class FinenkoConversionError(ValueError):
    """Raised when the archived Finenko 2026 collection is malformed."""


VARIANTS = {
    "d3-schofield": {"token": "D3", "procedure": "Schofield procedure"},
    "d4a-frommhold": {"token": "D4a", "procedure": "Frommhold procedure"},
}
UNIT_BASIS = (
    "The deposit uses the HCIA/HITRAN CIA block header and two-column data layout; "
    "that format defines the binary CIA coefficient as cm^5 molecule^-2."
)


def sha256(path: Path) -> str:
    """Return one file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_sources(source_dir: Path) -> dict[str, Path]:
    """Identify D3 and D4a from tolerant filenames, then validate their contents later."""
    files = sorted(path for path in source_dir.iterdir() if path.is_file()) if source_dir.is_dir() else []
    cia_files = [path for path in files if path.suffix.lower() == ".cia"]
    if len(files) != 2 or len(cia_files) != 2:
        raise FinenkoConversionError(f"expected exactly two archived .cia files; found {[path.name for path in files]}")
    found: dict[str, Path] = {}
    for path in cia_files:
        matches = [key for key, value in VARIANTS.items() if re.search(rf"(?:^|[-_(]){re.escape(value['token'])}(?:[-_().]|$)", path.name, re.IGNORECASE)]
        if len(matches) != 1 or matches[0] in found:
            raise FinenkoConversionError(f"cannot uniquely identify D3/D4a variant from {path.name!r}")
        found[matches[0]] = path
    if set(found) != set(VARIANTS):
        raise FinenkoConversionError("both D3 and D4a source variants are required")
    return found


def parse_source(path: Path) -> list[CIABlock]:
    """Parse and strictly validate one HITRAN-style non-HITRAN source."""
    blocks = parse_file(path, path.name)
    if not blocks:
        raise FinenkoConversionError(f"{path}: no CIA blocks")
    seen: set[tuple[float, float, float]] = set()
    for index, block in enumerate(blocks, start=1):
        if block.header_pair != "CH4-CO2":
            raise FinenkoConversionError(f"{path}: block {index}: unexpected pair {block.header_pair!r}")
        if block.reference_number != 0:
            raise FinenkoConversionError(f"{path}: block {index}: final header token is not 0")
        if block.resolution != 0.1:
            raise FinenkoConversionError(f"{path}: block {index}: resolution is not 0.1")
        if block.parsed_npoints != block.declared_npoints:
            raise FinenkoConversionError(f"{path}: block {index}: point-count mismatch")
        if any(len(point.raw_line.split()) != 2 for point in block.points):
            raise FinenkoConversionError(f"{path}: block {index}: data are not consistently two-column")
        if any(point.wavenumber < 0 for point in block.points):
            raise FinenkoConversionError(f"{path}: block {index}: negative wavenumber")
        if any(later.wavenumber <= earlier.wavenumber for earlier, later in zip(block.points, block.points[1:])):
            raise FinenkoConversionError(f"{path}: block {index}: non-monotonic wavenumber")
        key = (block.temperature, block.points[0].wavenumber, block.points[-1].wavenumber)
        if key in seen:
            raise FinenkoConversionError(f"{path}: block {index}: duplicate temperature/region")
        seen.add(key)
    return blocks


def _component(species: dict[str, dict[str, Any]], slug: str) -> dict[str, Any]:
    value = species[slug]
    return {key: value[key] for key in ("formula", "slug", "cas_registry_number")}


def descriptor(species: dict[str, dict[str, Any]], original_files: list[str], blocks: dict[str, list[CIABlock]]) -> dict[str, Any]:
    """Build the canonical long-CSV extra descriptor."""
    all_blocks = [block for values in blocks.values() for block in values]
    return {
        "collision_pair": {
            "formula": "CO2-CH4", "slug": "co2-ch4", "active_species_status": "unique",
            "active_species": "co2", "collider": "ch4",
            "components": [_component(species, "co2"), _component(species, "ch4")],
        },
        "dataset": {
            "id": "finenko2026", "recommendation_status": "supplementary",
            "repository": {
                "name": "JQSRT supplementary data", "version": None,
                "collection": "finenko2026", "original_files": original_files,
            },
            "collision_induced_absorption_xsecs": {
                "min_temperature": min(block.temperature for block in all_blocks),
                "max_temperature": max(block.temperature for block in all_blocks),
                "min_wavenumber": min(block.points[0].wavenumber for block in all_blocks),
                "max_wavenumber": max(block.points[-1].wavenumber for block in all_blocks),
                "wavenumber_resolution": 0.1,
                "units": {"temperature": "K", "wavenumber": "cm^-1", "wavenumber_resolution": "cm^-1"},
                "variant_descriptions": {key: value["procedure"] for key, value in VARIANTS.items()},
                "column_schemas": {"standard": [
                    {"name": "wavenumber", "units": "cm^-1"},
                    {"name": "cia_coefficient", "units": "cm^5 molecule^-2"},
                ]},
                "default_column_schema": "standard", "data_file": "CO2-CH4.csv",
            },
            "sources": ["finenko2026"],
        },
    }


def convert(source_dir: Path, output_dir: Path, metadata_dir: Path) -> dict[str, Any]:
    """Convert both procedure variants into one deterministic canonical dataset."""
    sources = discover_sources(source_dir)
    parsed = {variant: parse_source(path) for variant, path in sources.items()}
    temperatures = {variant: [block.temperature for block in blocks] for variant, blocks in parsed.items()}
    if len(set(tuple(values) for values in temperatures.values())) != 1:
        raise FinenkoConversionError("D3 and D4a temperature lists differ")
    bibliography = json.loads((metadata_dir / "sources.json").read_text(encoding="utf-8"))["finenko2026"]
    if bibliography.get("verified") is not True or bibliography.get("ref") is not None:
        raise FinenkoConversionError("finenko2026 must be a verified null-ref source")
    species = json.loads((metadata_dir / "species.json").read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "CO2-CH4.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["variant", "temperature", "wavenumber", "cia_coefficient"])
        for variant in VARIANTS:
            for block in parsed[variant]:
                temperature = str(int(block.temperature)) if block.temperature.is_integer() else str(block.temperature)
                writer.writerows((variant, temperature, point.wavenumber_text, point.cia_coefficient_text) for point in block.points)
    original_files = [sources[variant].name for variant in VARIANTS]
    json_path = output_dir / "CO2-CH4.json"
    json_path.write_text(json.dumps(descriptor(species, original_files, parsed), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    block_records = []
    for variant in VARIANTS:
        for index, block in enumerate(parsed[variant], start=1):
            block_records.append({
                "variant": variant, "source_file": sources[variant].name, "block_index": index,
                "temperature": block.temperature, "min_wavenumber": block.points[0].wavenumber,
                "max_wavenumber": block.points[-1].wavenumber, "npoints": len(block.points),
                "wavenumber_resolution": block.resolution, "header_reference_token": block.reference_number,
            })
    return {
        "source_files": [{"relative_path": f"source_data/non_hitran/finenko2026/{path.name}", "byte_size": path.stat().st_size, "sha256": sha256(path)} for path in sources.values()],
        "variant_meanings": {key: value["procedure"] for key, value in VARIANTS.items()},
        "coefficient_units": "cm^5 molecule^-2", "unit_determination_basis": UNIT_BASIS,
        "block_count": len(block_records), "blocks": block_records,
        "data_row_count": sum(record["npoints"] for record in block_records),
        "outputs": [{"path": path.name, "byte_size": path.stat().st_size, "sha256": sha256(path)} for path in (csv_path, json_path)],
        "validation_result": "passed",
    }
