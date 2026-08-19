from datetime import date, datetime, timezone

import pytest

from cia_pipeline.build_context import BuildContext
from cia_pipeline.versioning import is_valid_version, validate_version


def test_version_30_july_2026() -> None:
    context = BuildContext.from_date(date(2026, 7, 30))
    assert context.version == "20260730"


def test_version_1_august_2026_has_leading_zero() -> None:
    context = BuildContext.from_date(date(2026, 8, 1))
    assert context.version == "20260801"


def test_london_date_is_used_instead_of_utc_date() -> None:
    context = BuildContext.capture(
        lambda: datetime(2026, 7, 29, 23, 30, tzinfo=timezone.utc)
    )
    assert context.build_date == date(2026, 7, 30)
    assert context.version == "20260730"


def test_build_context_clock_is_captured_once() -> None:
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return datetime(2026, 7, 30, 23, 59, tzinfo=timezone.utc)

    context = BuildContext.capture(clock)
    assert calls == 1
    assert context.version == "20260731"  # Europe/London is already after midnight.
    assert calls == 1


def test_valid_yyyymmdd_version() -> None:
    assert is_valid_version("20260730")
    assert is_valid_version("20260801")


@pytest.mark.parametrize(
    "value", ["30072026", "20260230", "20261301", 20260730, None, "2026-07-30"]
)
def test_invalid_or_old_versions_are_rejected(value) -> None:
    assert not is_valid_version(value)
    with pytest.raises(ValueError):
        validate_version(value)
