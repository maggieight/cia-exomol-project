from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any

from .models import CIABlock, DataPoint, MetadataRegistry


class ExtradataError(ValueError):
    """Raised when canonical non-HITRAN input is malformed or unsafe."""


def discover_extra(input_root: Path) -> list[Path]:
    """Discover canonical extra descriptors under one source directory."""
    root = input_root / "extra"
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.glob("*/*.json")
        if path.is_file()
    )


def _safe_data_file(dataset_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ExtradataError("data_file must be a non-empty POSIX relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ExtradataError(f"unsafe data_file: {value!r}")
    if relative.suffix.lower() != ".csv":
        raise ExtradataError("data_file must currently use the .csv extension")
    resolved = dataset_dir / relative.as_posix()
    if not resolved.is_file():
        raise ExtradataError(f"data_file does not exist: {value}")
    return resolved


def _finite(token: str, label: str, row_number: int) -> float:
    if token == "":
        raise ExtradataError(f"row {row_number}: empty {label}")
    try:
        decimal = Decimal(token)
    except InvalidOperation as exc:
        raise ExtradataError(f"row {row_number}: non-numeric {label}: {token!r}") from exc
    if not decimal.is_finite():
        raise ExtradataError(f"row {row_number}: non-finite {label}: {token!r}")
    return float(decimal)


def detect_spectral_regions(
    points: list[DataPoint], nominal_step: float | None
) -> tuple[dict[str, Any], ...]:
    """Split sorted points at gaps larger than the declared nominal step."""
    if not points:
        return ()
    if nominal_step is None or nominal_step <= 0:
        return (
            {
                "min_wavenumber": points[0].wavenumber,
                "max_wavenumber": points[-1].wavenumber,
                "npoints": len(points),
            },
        )
    regions: list[list[DataPoint]] = [[points[0]]]
    tolerance = max(abs(nominal_step) * 1e-9, 1e-12)
    for earlier, later in zip(points, points[1:]):
        spacing = later.wavenumber - earlier.wavenumber
        if spacing < nominal_step - tolerance:
            raise ExtradataError(
                f"spacing {spacing} is smaller than nominal step {nominal_step}"
            )
        if spacing > nominal_step + tolerance:
            regions.append([])
        regions[-1].append(later)
    return tuple(
        {
            "min_wavenumber": region[0].wavenumber,
            "max_wavenumber": region[-1].wavenumber,
            "npoints": len(region),
        }
        for region in regions
    )


def validate_spectral_regions(
    regions: tuple[dict[str, Any], ...], points: list[DataPoint]
) -> None:
    """Validate ordered, non-overlapping regions and their point coverage."""
    if not regions or not points:
        raise ExtradataError("spectral regions and points must be non-empty")
    if sum(region["npoints"] for region in regions) != len(points):
        raise ExtradataError("spectral region point counts do not cover the file")
    if regions[0]["min_wavenumber"] != points[0].wavenumber:
        raise ExtradataError("first spectral region does not start at file minimum")
    if regions[-1]["max_wavenumber"] != points[-1].wavenumber:
        raise ExtradataError("last spectral region does not end at file maximum")
    for earlier, later in zip(regions, regions[1:]):
        if later["min_wavenumber"] <= earlier["max_wavenumber"]:
            raise ExtradataError("spectral regions overlap or are unsorted")


def _validate_descriptor(
    path: Path, payload: dict[str, Any], registry: MetadataRegistry
) -> tuple[dict[str, Any], dict[str, Any], Path, list[dict[str, Any]], str]:
    pair = payload.get("collision_pair")
    dataset = payload.get("dataset")
    if not isinstance(pair, dict) or not pair.get("formula") or not pair.get("slug"):
        raise ExtradataError(f"{path}: collision_pair formula and slug are required")
    components = pair.get("components")
    if not isinstance(components, list) or not components:
        raise ExtradataError(f"{path}: collision_pair components are required")
    for component in components:
        slug = component.get("slug") if isinstance(component, dict) else None
        species = registry.species.get(slug)
        if species is None:
            raise ExtradataError(f"{path}: unknown species component {slug!r}")
        for field in ("formula", "slug", "cas_registry_number"):
            if component.get(field) != species.get(field):
                raise ExtradataError(f"{path}: component {slug!r} {field} mismatch")
    if not isinstance(dataset, dict) or not dataset.get("id"):
        raise ExtradataError(f"{path}: dataset.id is required")
    dataset_id = dataset["id"]
    if path.parent.name != dataset_id:
        raise ExtradataError(f"{path}: parent directory must equal dataset.id")
    status = dataset.get("recommendation_status")
    if status not in {"recommended", "supplementary"}:
        raise ExtradataError(f"{path}: invalid recommendation_status")
    sources = dataset.get("sources")
    if (
        not isinstance(sources, list)
        or not sources
        or not all(isinstance(key, str) and key for key in sources)
        or len(sources) != len(set(sources))
    ):
        raise ExtradataError(f"{path}: sources must be a unique non-empty citation-key array")
    for key in sources:
        source = registry.sources.get(key)
        if source is None:
            raise ExtradataError(f"{path}: unknown source {key!r}")
        if source.get("verified") is not True or source.get("ref") is not None:
            raise ExtradataError(f"{path}: extradata source {key!r} must be verified with null ref")
    xsecs = dataset.get("collision_induced_absorption_xsecs")
    if not isinstance(xsecs, dict):
        raise ExtradataError(f"{path}: collision_induced_absorption_xsecs is required")
    if "files" in xsecs or "filename" in xsecs:
        raise ExtradataError(f"{path}: input JSON must not contain final output filenames")
    schemas = xsecs.get("column_schemas")
    default = xsecs.get("default_column_schema")
    if not isinstance(schemas, dict) or default not in schemas or len(schemas) != 1:
        raise ExtradataError(f"{path}: exactly one used default column schema is required")
    schema = schemas[default]
    if not isinstance(schema, list) or not schema:
        raise ExtradataError(f"{path}: default column schema must be a non-empty array")
    names = [column.get("name") for column in schema if isinstance(column, dict)]
    if len(names) != len(schema) or "wavenumber" not in names:
        raise ExtradataError(f"{path}: schema must contain named wavenumber column")
    for column in schema:
        if column.get("name") == "uncertainty":
            if column.get("uncertainty_type") != "absolute":
                raise ExtradataError(f"{path}: uncertainty must be absolute")
            if column.get("applies_to") not in names:
                raise ExtradataError(f"{path}: uncertainty applies_to is invalid")
    csv_path = _safe_data_file(path.parent, xsecs.get("data_file"))
    return pair, dataset, csv_path, schema, default


def _repository_record(
    path: Path,
    input_root: Path,
    dataset: dict[str, Any],
    registry: MetadataRegistry,
) -> dict[str, Any]:
    """Validate or derive stable provenance metadata for an extra dataset."""
    provenance_dir = input_root.parent / "source_data/non_hitran" / dataset["id"]
    supplied = dataset.get("repository")
    if supplied is None:
        names = {registry.sources[key]["repository"] for key in dataset["sources"]}
        if len(names) != 1:
            raise ExtradataError(f"{path}: extra sources must resolve to one repository name")
        original_files = (
            sorted(item.name for item in provenance_dir.iterdir() if item.is_file())
            if provenance_dir.is_dir()
            else []
        )
        supplied = {
            "name": next(iter(names)),
            "version": None,
            "collection": dataset["id"],
            "original_files": original_files,
        }
    if not isinstance(supplied, dict) or set(supplied) != {
        "name", "version", "collection", "original_files"
    }:
        raise ExtradataError(f"{path}: repository must contain name, version, collection, original_files")
    if not isinstance(supplied["name"], str) or not supplied["name"].strip():
        raise ExtradataError(f"{path}: repository.name must be non-empty")
    if supplied["version"] is not None:
        raise ExtradataError(f"{path}: non-HITRAN repository.version must be null")
    if supplied["collection"] != dataset["id"]:
        raise ExtradataError(f"{path}: repository.collection must equal dataset.id")
    originals = supplied["original_files"]
    if not isinstance(originals, list) or not originals or len(originals) != len(set(originals)):
        raise ExtradataError(f"{path}: repository.original_files must be unique and non-empty")
    for name in originals:
        relative = PurePosixPath(name) if isinstance(name, str) else None
        if (
            relative is None
            or relative.is_absolute()
            or len(relative.parts) != 1
            or ".." in relative.parts
            or "\\" in name
            or not (provenance_dir / name).is_file()
        ):
            raise ExtradataError(f"{path}: unsafe or missing repository original_file {name!r}")
    return {
        "name": supplied["name"],
        "version": None,
        "collection": supplied["collection"],
        "original_files": list(originals),
    }


def load_extradata_descriptor(
    path: Path, input_root: Path, registry: MetadataRegistry
) -> list[CIABlock]:
    """Load one canonical extradata descriptor and split its CSV by temperature."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtradataError(f"cannot read extradata JSON {path}: {exc}") from exc
    pair, dataset, csv_path, schema, default = _validate_descriptor(path, payload, registry)
    xsecs = dataset["collision_induced_absorption_xsecs"]
    csv_relative = csv_path.relative_to(input_root).as_posix()
    mapping = registry.dataset_files.get(csv_relative)
    if mapping is None:
        raise ExtradataError(f"{path}: data_file is not mapped in dataset_map.json: {csv_relative}")
    descriptor_components = tuple(component["slug"] for component in pair["components"])
    if (
        mapping.pair != pair["formula"]
        or mapping.active_species_status != pair.get("active_species_status")
        or mapping.active_species != pair.get("active_species")
        or mapping.collider != pair.get("collider")
        or mapping.components != descriptor_components
    ):
        raise ExtradataError(f"{path}: descriptor does not match dataset_map entry {csv_relative}")
    repository_record = _repository_record(path, input_root, dataset, registry)
    schema_names = [column["name"] for column in schema]
    expected_header = ["temperature", *schema_names]
    variant_header = ["variant", *expected_header]
    groups: dict[tuple[str | None, float], list[DataPoint]] = defaultdict(list)
    seen: set[tuple[str | None, str, str]] = set()
    previous_key: tuple[str, Decimal, Decimal] | None = None
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ExtradataError(f"{csv_path}: missing CSV header") from exc
        has_variant = header == variant_header
        if header != expected_header and not has_variant:
            raise ExtradataError(
                f"{csv_path}: CSV header {header!r} does not equal {expected_header!r} or {variant_header!r}"
            )
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ExtradataError(f"{csv_path}:{row_number}: malformed CSV row")
            if any(token == "" for token in row):
                raise ExtradataError(f"{csv_path}:{row_number}: empty data field")
            if has_variant:
                variant, temperature_text, *tokens = row
                if not variant:
                    raise ExtradataError(f"{csv_path}:{row_number}: empty variant")
            else:
                variant = None
                temperature_text, *tokens = row
            temperature = _finite(temperature_text, "temperature", row_number)
            values = [
                _finite(token, name, row_number)
                for name, token in zip(schema_names, tokens)
            ]
            wavenumber_index = schema_names.index("wavenumber")
            wavenumber_text = tokens[wavenumber_index]
            wavenumber = values[wavenumber_index]
            key = (variant, temperature_text, wavenumber_text)
            if key in seen:
                raise ExtradataError(f"{csv_path}:{row_number}: duplicate temperature+wavenumber")
            seen.add(key)
            decimal_key = (variant or "", Decimal(temperature_text), Decimal(wavenumber_text))
            if previous_key is not None and decimal_key <= previous_key:
                raise ExtradataError(f"{csv_path}:{row_number}: CSV is not strictly sorted")
            previous_key = decimal_key
            uncertainty = None
            uncertainty_text = None
            if "uncertainty" in schema_names:
                uncertainty_index = schema_names.index("uncertainty")
                uncertainty = values[uncertainty_index]
                uncertainty_text = tokens[uncertainty_index]
                if uncertainty < 0:
                    raise ExtradataError(f"{csv_path}:{row_number}: uncertainty is negative")
            data_values = [value for index, value in enumerate(values) if index != wavenumber_index]
            data_text = [token for index, token in enumerate(tokens) if index != wavenumber_index]
            groups[(variant, temperature)].append(
                DataPoint(
                    wavenumber_text=wavenumber_text,
                    cia_coefficient_text=data_text[0],
                    wavenumber=wavenumber,
                    cia_coefficient=data_values[0],
                    uncertainty_text=uncertainty_text,
                    uncertainty=uncertainty,
                    raw_line=" ".join(tokens),
                    data_tokens=tuple(tokens),
                )
            )
    if not groups:
        raise ExtradataError(f"{csv_path}: CSV contains no data rows")
    nominal_step = xsecs.get("nominal_wavenumber_step")
    if nominal_step is not None:
        nominal_step = float(nominal_step)
    blocks: list[CIABlock] = []
    for block_index, ((variant, temperature), points) in enumerate(groups.items(), start=1):
        if any(later.wavenumber <= earlier.wavenumber for earlier, later in zip(points, points[1:])):
            raise ExtradataError(f"{csv_path}: wavenumbers are not strictly increasing at {temperature} K")
        regions = detect_spectral_regions(points, nominal_step)
        validate_spectral_regions(regions, points)
        blocks.append(
            CIABlock(
                raw_relative_path=path.relative_to(input_root).as_posix(),
                source_path=csv_path,
                header_line_number=block_index,
                header_pair=pair["formula"],
                min_wavenumber=points[0].wavenumber,
                max_wavenumber=points[-1].wavenumber,
                declared_npoints=len(points),
                temperature=temperature,
                max_coefficient=max(point.cia_coefficient for point in points),
                resolution=(
                    float(xsecs["wavenumber_resolution"])
                    if xsecs.get("wavenumber_resolution") is not None
                    else None
                ),
                resolution_raw=(
                    str(xsecs["wavenumber_resolution"])
                    if xsecs.get("wavenumber_resolution") is not None
                    else ""
                ),
                description=None,
                reference_number=None,
                points=points,
                collection="extra",
                normalized_pair=pair["formula"],
                active_species_status=pair.get("active_species_status", ""),
                active_species=pair.get("active_species"),
                collider=pair.get("collider"),
                components=tuple(component["slug"] for component in pair["components"]),
                variant=variant,
                citation_keys=tuple(dataset["sources"]),
                input_kind="extradata",
                explicit_dataset_id=dataset["id"],
                recommendation_status=dataset["recommendation_status"],
                collision_pair_record=pair,
                column_schemas=xsecs["column_schemas"],
                default_column_schema=default,
                input_xsecs_metadata={
                    key: value
                    for key, value in xsecs.items()
                    if key not in {"column_schemas", "default_column_schema", "data_file"}
                },
                spectral_regions=regions,
                repository_record=repository_record,
            )
        )
    actual_min_t = min(key[1] for key in groups)
    actual_max_t = max(key[1] for key in groups)
    actual_min_w = min(point.wavenumber for points in groups.values() for point in points)
    actual_max_w = max(point.wavenumber for points in groups.values() for point in points)
    for key, actual in (
        ("min_temperature", actual_min_t),
        ("max_temperature", actual_max_t),
        ("min_wavenumber", actual_min_w),
        ("max_wavenumber", actual_max_w),
    ):
        if float(xsecs.get(key)) != actual:
            raise ExtradataError(f"{path}: {key} does not match CSV ({xsecs.get(key)} != {actual})")
    return blocks


def load_extra(input_root: Path, registry: MetadataRegistry) -> list[CIABlock]:
    """Discover and load all canonical extra descriptors."""
    blocks: list[CIABlock] = []
    for path in discover_extra(input_root):
        blocks.extend(load_extradata_descriptor(path, input_root, registry))
    return blocks
