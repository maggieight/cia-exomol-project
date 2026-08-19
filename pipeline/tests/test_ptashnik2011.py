from pathlib import Path

import pytest

from cia_pipeline.ptashnik2011 import (
    TEMPERATURES,
    ExtractionError,
    csv_bytes,
    logical_rows,
    validate_column_tokens,
)


def columns(fill: str = "1.00E-22") -> list[list[str]]:
    waves = [str(2010 + 10 * index) for index in range(633)]
    result = [waves]
    for _ in TEMPERATURES:
        result.extend([[fill] * 633, ["2.0E-23"] * 633])
    return result


def test_13_column_mapping_and_equal_lengths() -> None:
    data = columns()
    validate_column_tokens(data)
    rows = logical_rows(data)
    assert rows[0].temperature == 293
    assert rows[0].wavenumber == "2010"
    assert rows[633].temperature == 350


def test_unequal_token_lengths_fail() -> None:
    data = columns()
    data[-1].pop()
    with pytest.raises(ExtractionError, match="token counts differ"):
        validate_column_tokens(data)


def test_paired_missing_values_are_omitted() -> None:
    data = columns()
    data[1][0] = data[2][0] = "--"
    rows = logical_rows(data)
    assert len(rows) == 6 * 633 - 1
    assert not any(row.temperature == 293 and row.wavenumber == "2010" for row in rows)


def test_incomplete_pair_fails_with_location() -> None:
    data = columns()
    data[1][0] = "--"
    with pytest.raises(ExtractionError, match="293 K, 2010"):
        logical_rows(data)


def test_scientific_notation_is_preserved_and_output_is_sorted() -> None:
    data = columns()
    data[1][0] = "1.760E-22"
    rows = logical_rows(data)
    payload = csv_bytes(rows).decode()
    assert "293,2010,1.760E-22,2.0E-23\n" in payload
    keys = [(row.temperature, int(row.wavenumber)) for row in rows]
    assert keys == sorted(keys)
