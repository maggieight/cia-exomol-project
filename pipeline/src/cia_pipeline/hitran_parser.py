"""Parse the HITRAN.cia.txt files"""

from __future__ import annotations

import math
import re
from pathlib import Path

from .models import CIABlock, CIAParseError, DataPoint

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
HEADER_RE = re.compile(
    rf"^\s*(?P<pair>.+?)\s+"
    rf"(?P<minimum>{NUMBER})\s+(?P<maximum>{NUMBER})\s+"
    rf"(?P<npoints>\d+)\s+(?P<temperature>{NUMBER})\s+"
    rf"(?P<max_coefficient>{NUMBER})\s+(?P<resolution>{NUMBER})"
    rf"(?:\s+(?P<tail>.*?))?\s*$"
)
NUMBER_RE = re.compile(rf"^{NUMBER}$")
REPOSITORY_VERSION_RE = re.compile(r"_(?P<version>\d{4})\.cia\.txt$", re.I)


def parse_header(line: str, path: Path, line_number: int) -> dict[str, object]:
    match = HEADER_RE.match(line)
    if not match:
        raise CIAParseError(path, line_number, "problematic HITRAN CIA header")
    tail = (match.group("tail") or "").strip()
    if not tail:
        raise CIAParseError(path, line_number, "header has no trailing reference number")
    tail_parts = tail.rsplit(maxsplit=1)
    try:
        reference_number = int(tail_parts[-1])
    except ValueError as exc:
        raise CIAParseError(
            path, line_number, "header does not end in an integer reference number"
        ) from exc
    description = tail_parts[0].strip() if len(tail_parts) == 2 else None
    resolution_raw = match.group("resolution")
    resolution_value = float(resolution_raw)
    return {
        "header_pair": match.group("pair"),
        "min_wavenumber": float(match.group("minimum")),
        "max_wavenumber": float(match.group("maximum")),
        "declared_npoints": int(match.group("npoints")),
        "temperature": float(match.group("temperature")),
        "max_coefficient": float(match.group("max_coefficient")),
        "resolution": resolution_value if resolution_value >= 0 else None,
        "resolution_raw": resolution_raw,
        "description": description,
        "reference_number": reference_number,
    }


def parse_repository_version(filename: str) -> str:
    match = REPOSITORY_VERSION_RE.search(filename)
    if not match:
        raise ValueError(f"cannot parse repository version from {filename!r}")
    return match.group("version")


def parse_file(path: Path, raw_relative_path: str | None = None) -> list[CIABlock]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    blocks: list[CIABlock] = []
    index = 0
    relative = raw_relative_path or path.name
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        header_line_number = index + 1
        header = parse_header(lines[index], path, header_line_number)
        index += 1
        points: list[DataPoint] = []
        declared = int(header["declared_npoints"])
        expected_column_count: int | None = None
        block_index = len(blocks) + 1
        for point_offset in range(declared):
            if index >= len(lines):
                raise CIAParseError(
                    path,
                    header_line_number,
                    f"point-count mismatch: declared {declared}, parsed {len(points)} before EOF",
                )
            columns = lines[index].split()
            if HEADER_RE.match(lines[index]):
                raise CIAParseError(
                    path,
                    index + 1,
                    f"point-count mismatch for header at line {header_line_number}: "
                    f"declared {declared}, parsed {len(points)}; encountered a new header",
                )
            actual_column_count = len(columns)
            if actual_column_count not in (2, 3):
                raise CIAParseError(
                    path,
                    index + 1,
                    f"block {block_index} (header line {header_line_number}) data row "
                    f"must contain 2 or 3 columns; actual column count "
                    f"{actual_column_count}",
                )
            if expected_column_count is None:
                expected_column_count = actual_column_count
            elif actual_column_count != expected_column_count:
                raise CIAParseError(
                    path,
                    index + 1,
                    f"block {block_index} (header line {header_line_number}) has mixed "
                    f"data-column counts: expected {expected_column_count}, actual "
                    f"{actual_column_count}",
                )
            wavenumber_text, cia_coefficient_text = columns[:2]
            if not NUMBER_RE.match(wavenumber_text):
                raise CIAParseError(path, index + 1, "wavenumber is not numeric")
            if not NUMBER_RE.match(cia_coefficient_text):
                raise CIAParseError(path, index + 1, "CIA coefficient is not numeric")
            uncertainty_text = columns[2] if actual_column_count == 3 else None
            if uncertainty_text is not None and not NUMBER_RE.match(uncertainty_text):
                raise CIAParseError(
                    path, index + 1, "uncertainty is not a numeric value"
                )
            wavenumber = float(wavenumber_text)
            cia_coefficient = float(cia_coefficient_text)
            uncertainty = (
                float(uncertainty_text) if uncertainty_text is not None else None
            )
            if (
                not math.isfinite(wavenumber)
                or not math.isfinite(cia_coefficient)
                or (uncertainty is not None and not math.isfinite(uncertainty))
            ):
                raise CIAParseError(path, index + 1, "non-finite numerical value")
            if uncertainty is not None and uncertainty < 0:
                raise CIAParseError(path, index + 1, "uncertainty must not be negative")
            points.append(
                DataPoint(
                    wavenumber_text=wavenumber_text,
                    cia_coefficient_text=cia_coefficient_text,
                    wavenumber=wavenumber,
                    cia_coefficient=cia_coefficient,
                    uncertainty_text=uncertainty_text,
                    uncertainty=uncertainty,
                    raw_line=lines[index],
                )
            )
            index += 1
        block = CIABlock(
            raw_relative_path=relative,
            source_path=path,
            header_line_number=header_line_number,
            points=points,
            header_text=lines[header_line_number - 1],
            **header,
        )
        if any(
            later.wavenumber <= earlier.wavenumber
            for earlier, later in zip(points, points[1:])
        ):
            block.warnings.append("non-monotonic wavenumbers")
        if points and (
            points[0].wavenumber != block.min_wavenumber
            or points[-1].wavenumber != block.max_wavenumber
        ):
            block.warnings.append(
                "header wavenumber endpoints differ from first/last numerical rows"
            )
        if block.resolution is None:
            block.warnings.append(
                f"source resolution unavailable (sentinel {block.resolution_raw})"
            )
        blocks.append(block)
    return blocks
