from __future__ import annotations

import json
from pathlib import Path

import pytest

from cia_pipeline.finenko2026 import VARIANTS, convert, discover_sources, parse_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source_data/non_hitran/finenko2026"


def test_discovers_two_procedure_variants_by_tolerant_names() -> None:
    found = discover_sources(SOURCE)
    assert set(found) == {"d3-schofield", "d4a-frommhold"}
    assert found["d3-schofield"].name == "CH4-CO2-D3.cia"
    assert found["d4a-frommhold"].name == "CH4-CO2-D4a.cia"


def test_hitran_style_extra_blocks_headers_counts_and_resolution() -> None:
    for path in discover_sources(SOURCE).values():
        blocks = parse_source(path)
        assert len(blocks) == 34
        assert [block.temperature for block in blocks] == list(range(70, 401, 10))
        assert all(block.header_pair == "CH4-CO2" and block.resolution == 0.1 for block in blocks)
        assert all(block.reference_number == 0 and block.declared_npoints == block.parsed_npoints for block in blocks)


def test_converter_preserves_variants(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report = convert(SOURCE, output, ROOT / "metadata")
    assert report["block_count"] == 68
    descriptor = json.loads((output / "CO2-CH4.json").read_text())
    assert descriptor["collision_pair"]["formula"] == "CO2-CH4"
    assert descriptor["dataset"]["id"] == "finenko2026"
    assert descriptor["dataset"]["collision_induced_absorption_xsecs"]["variant_descriptions"] == {
        key: value["procedure"] for key, value in VARIANTS.items()
    }


def test_source_is_verified_null_ref_and_not_hitran_indexed() -> None:
    from cia_pipeline.metadata import load_metadata
    registry = load_metadata(ROOT / "metadata", strict=True)
    assert registry.sources["finenko2026"]["ref"] is None
    assert all("finenko2026" not in keys for keys in registry.references.values())


@pytest.mark.parametrize("bad_line", ["bad header", "CH4-CO2 0 1 2 70 1 0.1 0"])
def test_malformed_header_or_point_count_fails(tmp_path: Path, bad_line: str) -> None:
    source = SOURCE / "CH4-CO2-D3.cia"
    target = tmp_path / source.name
    lines = source.read_text().splitlines()
    lines[0] = bad_line
    target.write_text("\n".join(lines) + "\n")
    with pytest.raises(Exception):
        parse_source(target)
