"""check and validate raw metadata"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import DatasetMapEntry, MetadataRegistry

SOURCE_REQUIRED_FIELDS = {
    "repository",
    "citation_key",
    "authors",
    "title",
    "year",
    "doi",
    "source_url",
    "verified",
    "ref",
}

SHARED_HITRAN_SOURCE_IDS = (
    "hitran_cia_repository",
    "terragni_hitran",
    "gordon2026_hitran",
)


def validate_sources(
    sources: dict[str, dict[str, Any]], strict: bool = False
) -> tuple[dict[int, tuple[str, ...]], list[dict[str, Any]]]:
    """Validate source records and build the HITRAN-only reference index."""
    problems: list[dict[str, Any]] = []
    reverse: dict[int, list[str]] = defaultdict(list)
    citation_keys: set[str] = set()
    for key, record in sources.items():
        citation_key = record.get("citation_key")
        if citation_key != key:
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "key does not equal citation_key"}
            )
        if isinstance(citation_key, str) and citation_key in citation_keys:
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "duplicate citation_key"}
            )
        if isinstance(citation_key, str):
            citation_keys.add(citation_key)
        missing = sorted(SOURCE_REQUIRED_FIELDS - record.keys())
        if missing:
            problems.append(
                {
                    "registry": "sources.json",
                    "key": key,
                    "problem": f"missing required fields: {', '.join(missing)}",
                }
            )
        authors = record.get("authors")
        if not isinstance(authors, list) or not authors or not all(
            isinstance(author, str) and author.strip() for author in authors
        ):
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "authors must be a non-empty string array"}
            )
        doi = record.get("doi")
        if doi is not None and (not isinstance(doi, str) or not doi.strip()):
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "doi must be a non-empty string or null"}
            )
        verified = record.get("verified")
        if not isinstance(verified, bool):
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "verified must be boolean"}
            )
        elif strict and not verified:
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "source is not verified"}
            )
        repository = record.get("repository")
        ref = record.get("ref")
        if key in SHARED_HITRAN_SOURCE_IDS:
            if repository != "HITRAN CIA":
                problems.append(
                    {"registry": "sources.json", "key": key, "problem": "shared HITRAN source must use the HITRAN CIA repository"}
                )
            if ref is not None:
                problems.append(
                    {"registry": "sources.json", "key": key, "problem": "shared HITRAN source ref must be null"}
                )
        elif repository == "HITRAN CIA":
            if not isinstance(ref, int) or isinstance(ref, bool) or ref <= 0:
                problems.append(
                    {"registry": "sources.json", "key": key, "problem": "HITRAN CIA ref must be a positive integer"}
                )
            else:
                reverse[ref].append(key)
        elif ref is not None:
            problems.append(
                {"registry": "sources.json", "key": key, "problem": "non-HITRAN ref must be null"}
            )
    return (
        {ref: tuple(sorted(keys)) for ref, keys in reverse.items()},
        problems,
    )


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_metadata(metadata_dir: Path, strict: bool = False) -> MetadataRegistry:
    species = _read_json(metadata_dir / "species.json")
    sources = _read_json(metadata_dir / "sources.json")
    dataset_map = _read_json(metadata_dir / "dataset_map.json")
    problems: list[dict[str, Any]] = []

    for slug, record in species.items():
        for field in ("formula", "slug", "cas_registry_number"):
            if field not in record:
                problems.append(
                    {"registry": "species.json", "key": slug, "problem": f"missing field {field}"}
                )
        if record.get("slug") != slug:
            problems.append(
                {"registry": "species.json", "key": slug, "problem": "key does not equal slug"}
            )
        if record.get("cas_registry_number") is None and record.get(
            "cas_registry_number_status"
        ) != "not_applicable_mixture":
            problems.append(
                {
                    "registry": "species.json",
                    "key": slug,
                    "problem": "null CAS Registry Number is not explicitly not applicable",
                }
            )

    references, source_problems = validate_sources(sources, strict=strict)
    problems.extend(source_problems)

    entries: dict[str, DatasetMapEntry] = {}
    for raw_path, record in dataset_map.get("files", {}).items():
        entries[raw_path] = DatasetMapEntry(
            raw_relative_path=raw_path,
            pair=record["pair"],
            active_species_status=record["active_species_status"],
            active_species=record.get("active_species"),
            collider=record.get("collider"),
            components=tuple(record.get("components", ())),
            variant=record.get("variant"),
        )
        component_slugs = record.get("components") or [
            record.get("active_species"),
            record.get("collider"),
        ]
        for component_slug in filter(None, component_slugs):
            if component_slug not in species:
                problems.append(
                    {
                        "registry": "dataset_map.json",
                        "key": raw_path,
                        "problem": f"missing species {component_slug!r}",
                    }
                )
    return MetadataRegistry(
        species=species,
        sources=sources,
        dataset_files=entries,
        references=references,
        problems=problems,
    )
