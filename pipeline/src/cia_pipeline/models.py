"""Define the data structures used internally by the pipeline"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STANDARD_COLUMN_SCHEMA: list[dict[str, str]] = [
    {"name": "wavenumber", "units": "cm^-1"},
    {"name": "cia_coefficient", "units": "cm^5 molecule^-2"},
]

ABSOLUTE_UNCERTAINTY_COLUMN_SCHEMA: list[dict[str, str]] = [
    *STANDARD_COLUMN_SCHEMA,
    {
        "name": "uncertainty",
        "units": "cm^5 molecule^-2",
        "uncertainty_type": "absolute",
        "applies_to": "cia_coefficient",
    },
]


@dataclass(frozen=True)
class DataPoint:
    wavenumber_text: str
    cia_coefficient_text: str
    wavenumber: float
    cia_coefficient: float
    uncertainty_text: str | None = None
    uncertainty: float | None = None
    raw_line: str = ""
    data_tokens: tuple[str, ...] = ()


@dataclass
class CIABlock:
    raw_relative_path: str
    source_path: Path
    header_line_number: int
    header_pair: str
    min_wavenumber: float
    max_wavenumber: float
    declared_npoints: int
    temperature: float
    max_coefficient: float
    resolution: float | None
    resolution_raw: str
    description: str | None
    reference_number: int | None
    points: list[DataPoint]
    header_text: str = ""
    collection: str = ""
    repository_version: str = ""
    normalized_pair: str = ""
    active_species_status: str = ""
    active_species: str | None = None
    collider: str | None = None
    components: tuple[str, ...] = ()
    variant: str | None = None
    citation_keys: tuple[str, ...] = ()
    proposed_dataset_group: str | None = None
    proposed_dataset_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    input_kind: str = "hitran"
    explicit_dataset_id: str | None = None
    recommendation_status: str | None = None
    collision_pair_record: dict[str, Any] | None = None
    column_schemas: dict[str, list[dict[str, Any]]] | None = None
    default_column_schema: str | None = None
    input_xsecs_metadata: dict[str, Any] | None = None
    spectral_regions: tuple[dict[str, Any], ...] = ()
    repository_record: dict[str, Any] | None = None

    @property
    def parsed_npoints(self) -> int:
        return len(self.points)

    def inventory_dict(self) -> dict[str, Any]:
        return {
            "raw_relative_path": self.raw_relative_path,
            "source_filename": self.source_path.name,
            "header_line_number": self.header_line_number,
            "collection": self.collection,
            "repository_version": self.repository_version,
            "normalized_pair": self.normalized_pair,
            "header_pair": self.header_pair,
            "temperature": self.temperature,
            "wavenumber_range": {
                "minimum": self.min_wavenumber,
                "maximum": self.max_wavenumber,
            },
            "source_provided_resolution": self.resolution,
            "source_resolution_raw": self.resolution_raw,
            "declared_point_count": self.declared_npoints,
            "parsed_point_count": self.parsed_npoints,
            "data_column_count": (
                3
                if self.points and self.points[0].uncertainty is not None
                else 2
            ),
            "has_uncertainty": bool(
                self.points and self.points[0].uncertainty is not None
            ),
            "reference_number": self.reference_number,
            "resolved_citation_keys": list(self.citation_keys),
            "active_species_status": self.active_species_status,
            "active_species": self.active_species,
            "collider": self.collider,
            "components": list(self.components),
            "variant": self.variant,
            "description": self.description,
            "proposed_dataset_group": self.proposed_dataset_group,
            "proposed_dataset_id": self.proposed_dataset_id,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class DatasetMapEntry:
    raw_relative_path: str
    pair: str
    active_species_status: str
    active_species: str | None
    collider: str | None
    components: tuple[str, ...]
    variant: str | None


@dataclass
class MetadataRegistry:
    species: dict[str, dict[str, Any]]
    sources: dict[str, dict[str, Any]]
    dataset_files: dict[str, DatasetMapEntry]
    references: dict[int, tuple[str, ...]]
    problems: list[dict[str, Any]]


class CIAParseError(ValueError):
    def __init__(self, path: Path, line_number: int, message: str):
        self.path = path
        self.line_number = line_number
        self.message = message
        super().__init__(f"{path}:{line_number}: {message}")
