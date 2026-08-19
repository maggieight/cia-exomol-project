from __future__ import annotations

import json
from pathlib import Path

from cia_pipeline.dong2026 import convert as convert_dong, parse_source as parse_dong
from cia_pipeline.vitali2026 import EXPECTED, TEMPERATURES, convert as convert_vitali, parse_source as parse_vitali

ROOT = Path(__file__).resolve().parents[1]


def test_dong_whitespace_source_and_combined_standard_uncertainty() -> None:
    rows = parse_dong(ROOT / "source_data/non_hitran/dong2026/CIA B_O2-O2_1.06um.txt")
    assert len(rows) == 70001 and rows[0][0] == "9120" and rows[-1][0] == "9820"
    assert all(len(row) == 3 for row in rows)


def test_vitali_comma_sources_regions_zero_and_large_uncertainty() -> None:
    found_zero = found_larger_uncertainty = False
    for temperature in TEMPERATURES:
        rows = parse_vitali(ROOT / f"source_data/non_hitran/vitali2026/BAC_CIA_CO2_H2_{temperature}K.txt", temperature)
        assert len(rows) == EXPECTED[temperature][0]
        found_zero |= any(float(row[1]) == 0 for row in rows)
        found_larger_uncertainty |= any(float(row[2]) > float(row[1]) for row in rows)
    assert found_zero and found_larger_uncertainty


def test_both_converters_generate_canonical_outputs(tmp_path: Path) -> None:
    for name, converter in (("dong2026", convert_dong), ("vitali2026", convert_vitali)):
        output = tmp_path / name
        report = converter(
            ROOT / f"source_data/non_hitran/{name}", output, ROOT / "metadata"
        )
        assert report["validation_result"] == "passed"
        assert list(output.glob("*.json")) and list(output.glob("*.csv"))


def test_canonical_uncertainty_semantics_and_resolution() -> None:
    dong = json.loads((ROOT / "input/extra/dong2026/O2-O2.json").read_text())
    vitali = json.loads((ROOT / "input/extra/vitali2026/CO2-H2.json").read_text())
    dx = dong["dataset"]["collision_induced_absorption_xsecs"]
    vx = vitali["dataset"]["collision_induced_absorption_xsecs"]
    du = dx["column_schemas"][dx["default_column_schema"]][-1]
    vu = vx["column_schemas"][vx["default_column_schema"]][-1]
    assert dx["wavenumber_resolution"] is None and dx["nominal_wavenumber_step"] == 0.01
    assert du["uncertainty_type"] == "absolute" and du["uncertainty_level"] == "1_sigma"
    assert vx["wavenumber_resolution"] == vx["nominal_wavenumber_step"] == 1
    assert vu["uncertainty_type"] == "absolute" and vu["uncertainty_category"] == "systematic"


def test_existing_pair_metadata_and_supplementary_status() -> None:
    dong = json.loads((ROOT / "input/extra/dong2026/O2-O2.json").read_text())
    vitali = json.loads((ROOT / "input/extra/vitali2026/CO2-H2.json").read_text())
    assert (dong["collision_pair"]["active_species"], dong["collision_pair"]["collider"]) == ("o2", "o2")
    assert (vitali["collision_pair"]["active_species"], vitali["collision_pair"]["collider"]) == ("co2", "h2")
    assert dong["dataset"]["recommendation_status"] == vitali["dataset"]["recommendation_status"] == "supplementary"
