from pathlib import Path

import pytest

from cia_pipeline.cli import CONVERTERS, build_parser


@pytest.mark.parametrize("converter", sorted(CONVERTERS))
def test_convert_subcommands_are_available(converter: str) -> None:
    args = build_parser().parse_args([
        "convert",
        converter,
        "--source",
        "source",
        "--output",
        "output",
        "--metadata",
        "metadata",
    ])
    assert args.command == "convert"
    assert args.converter == converter
    assert args.source == Path("source")
    assert args.output == Path("output")
    assert args.metadata == Path("metadata")


def test_non_ptashnik_converter_accepts_optional_report() -> None:
    args = build_parser().parse_args([
        "convert",
        "dong2026",
        "--source",
        "source",
        "--output",
        "output",
        "--metadata",
        "metadata",
        "--report",
        "conversion.json",
    ])
    assert args.report == Path("conversion.json")
