from pathlib import Path

import pytest

from cia_pipeline.hitran_parser import parse_file, parse_repository_version
from cia_pipeline.models import CIAParseError


def test_valid_single_block(tmp_path: Path) -> None:
    raw = tmp_path / "CO2-CH4_2024.cia.txt"
    raw.write_text(
        " CO2-CH4 0.042 0.085 2 100 1.0E-43 0.042 Model. 47\n"
        " 0.0420 2.5413E-48\n"
        " 0.0850 1.0164E-47\n"
    )
    block = parse_file(raw)[0]
    assert block.declared_npoints == block.parsed_npoints == 2
    assert block.description == "Model."
    assert block.reference_number == 47
    assert block.points[0].wavenumber_text == "0.0420"


def test_multiple_blocks_and_sentinel(tmp_path: Path) -> None:
    raw = tmp_path / "H2-CH4_eq_2011.cia.txt"
    raw.write_text(
        " H2-CH4 0.020 1.000 2 40.0 6.9E-43 -.999 Equilibrium 16\n"
        " .020 1E-44\n 1.000 2E-44\n"
        " H2-CH4 0.020 1.000 2 51.7 5E-43 -.999 Equilibrium 16\n"
        " .020 2E-44\n 1.000 3E-44\n"
    )
    blocks = parse_file(raw)
    assert len(blocks) == 2
    assert blocks[0].resolution is None
    assert blocks[1].temperature == 51.7


def test_truncated_block_fails(tmp_path: Path) -> None:
    raw = tmp_path / "x_2024.cia.txt"
    raw.write_text(" A-B 0 2 2 100 1E-5 1.0 7\n 0 1E-5\n")
    with pytest.raises(CIAParseError, match="point-count mismatch"):
        parse_file(raw)


def test_repository_version() -> None:
    assert parse_repository_version("CO2-Ar_2021.cia.txt") == "2021"


def test_spaced_pair_label_and_extra_column(tmp_path: Path) -> None:
    raw = tmp_path / "H2-H2_eq_2018.cia.txt"
    raw.write_text(
        " eq-H2 -- eq-H2 0.25 0.50 2 40 3.6e-44 -.999 34\n"
        " 0.25 4.7E-51 1.0E-52\n"
        " 0.50 1.9E-50 2.0E-52\n"
    )
    block = parse_file(raw)[0]
    assert block.header_pair == "eq-H2 -- eq-H2"
    assert block.points[0].uncertainty_text == "1.0E-52"
    assert block.points[0].uncertainty == 1.0e-52
    assert block.reference_number == 34


def test_reference_code_three_is_not_a_column_count(tmp_path: Path) -> None:
    raw = tmp_path / "N2-N2_2021.cia.txt"
    raw.write_text(
        " N2-N2 1999.9 2000.4 3 228.2 3.211E-45 0.500 0-10atm 3\n"
        " 1999.9000 2.201E-47 2.119E-48\n"
        " 2000.1500 2.127E-47 1.469E-48\n"
        " 2000.4000 1.747E-47 2.077E-48\n"
    )
    block = parse_file(raw)[0]
    assert block.reference_number == 3
    assert all(point.uncertainty is not None for point in block.points)


def test_mixed_two_and_three_columns_fails(tmp_path: Path) -> None:
    raw = tmp_path / "mixed_2024.cia.txt"
    raw.write_text(
        " N2-N2 0 1 2 228.2 1E-45 0.5 0-10atm 3\n"
        " 0 1E-47\n"
        " 1 2E-47 3E-48\n"
    )
    with pytest.raises(CIAParseError, match="mixed data-column counts.*actual 3"):
        parse_file(raw)


@pytest.mark.parametrize("uncertainty", ["-1E-48", "not-a-number"])
def test_invalid_uncertainty_fails(tmp_path: Path, uncertainty: str) -> None:
    raw = tmp_path / "bad_2024.cia.txt"
    raw.write_text(
        " N2-N2 0 0 1 228.2 1E-45 0.5 0-10atm 3\n"
        f" 0 1E-47 {uncertainty}\n"
    )
    with pytest.raises(CIAParseError, match="uncertainty"):
        parse_file(raw)
