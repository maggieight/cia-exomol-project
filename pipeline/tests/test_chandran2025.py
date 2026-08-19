from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cia_pipeline.chandran2025 import (
    ChandranConversionError,
    SPECS,
    convert,
    expected_files,
    parse_source,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source_data/non_hitran/chandran2025"


def test_expected_collection_and_canonical_orientation() -> None:
    assert set(path.name for path in SOURCE.glob("*.data")) == set(expected_files())
    assert [(spec.header_pair, spec.canonical_pair) for spec in SPECS] == [
        ("Ar-He", "Ar-He"), ("Ne-Ar", "Ar-Ne"), ("Ne-He", "He-Ne")
    ]


def test_real_source_parsing_counts_ranges_and_uncertainty() -> None:
    for filename, (spec, temperature) in expected_files().items():
        rows = parse_source(SOURCE / filename, spec, temperature)
        assert len(rows) == spec.npoints
        assert rows[0][0] == "5" and rows[-1][0] == str(spec.maximum)
        assert all(len(row) == 3 and float(row[2]) >= 0 for row in rows)


def test_converter_outputs_are_canonical(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report = convert(SOURCE, output, ROOT / "metadata")
    assert report["data_row_count"] == 7200
    assert report["temperature_group_count"] == 11
    for descriptor in output.glob("*.json"):
        payload = json.loads(descriptor.read_text())
        pair = payload["collision_pair"]
        assert pair["active_species_status"] == "no_unique_active_species"
        assert pair["active_species"] is None and pair["collider"] is None
        assert payload["dataset"]["sources"] == ["chandran2025"]


def test_missing_and_unexpected_files_fail(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    (source / next(iter(expected_files()))).unlink()
    with pytest.raises(ChandranConversionError, match="source collection mismatch"):
        convert(source, tmp_path / "out", ROOT / "metadata")
    shutil.rmtree(source)
    shutil.copytree(SOURCE, source)
    (source / "unexpected.data").write_text("x")
    with pytest.raises(ChandranConversionError, match="source collection mismatch"):
        convert(source, tmp_path / "out", ROOT / "metadata")


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("//Data for CIA of Wrong-X at 165 K", "header pair"),
        ("//Data for CIA of Ar-He at 295 K", "temperature mismatch"),
    ],
)
def test_header_pair_and_temperature_mismatch_fail(tmp_path: Path, replacement: str, message: str) -> None:
    spec = SPECS[0]
    source = SOURCE / "CIA_HeAr_165K.data"
    path = tmp_path / source.name
    lines = source.read_text().splitlines()
    lines[0] = replacement
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ChandranConversionError, match=message):
        parse_source(path, spec, 165)


def test_bad_columns_negative_nonfinite_and_nonmonotonic_fail(tmp_path: Path) -> None:
    spec = SPECS[0]
    source = SOURCE / "CIA_HeAr_165K.data"
    for token_line, message in [
        ("5 1", "expected 3 columns"),
        ("5 1 -1", "negative"),
        ("5 NaN 1", "non-finite"),
        ("0 1 1", "grid step"),
    ]:
        path = tmp_path / f"{message.replace(' ', '_')}.data"
        lines = source.read_text().splitlines()
        lines[6] = token_line
        path.write_text("\n".join(lines) + "\n")
        with pytest.raises(ChandranConversionError, match=message):
            parse_source(path, spec, 165)
