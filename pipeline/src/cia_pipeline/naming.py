from __future__ import annotations

import math
import re
from collections import Counter
from decimal import Decimal

from .models import CIABlock


def temperature_token(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return _decimal_token(value)


def _decimal_token(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def dataset_metadata_filename(
    pair: str,
    dataset_id: str,
    minimum: float,
    maximum: float,
    min_temperature: float,
    max_temperature: float,
) -> str:
    return (
        f"{pair}_{dataset_id}_{math.floor(minimum)}_{math.ceil(maximum)}_"
        f"{math.floor(min_temperature)}_{math.ceil(max_temperature)}.json"
    )


def proposed_cia_filenames(
    pair: str, dataset_id: str, blocks: list[CIABlock]
) -> list[str]:
    """Return one deterministic, collision-free proposed filename per block."""
    bases = [
        (
            f"{pair}_{dataset_id}_{math.floor(block.min_wavenumber)}_"
            f"{math.ceil(block.max_wavenumber)}_{temperature_token(block.temperature)}"
        )
        for block in blocks
    ]
    base_counts = Counter(bases)
    candidates: list[str] = []
    for base, block in zip(bases, blocks):
        name = base
        if base_counts[base] > 1 and block.variant:
            name += f"_{_safe_suffix(block.variant)}"
        candidates.append(name)

    counts = Counter(candidates)
    refined: list[str] = []
    for name, block in zip(candidates, blocks):
        if counts[name] > 1:
            name += (
                f"_{_decimal_token(block.max_wavenumber)}"
                f"_r{_decimal_token(block.min_wavenumber)}"
            )
        refined.append(name)

    counts = Counter(refined)
    resolved: list[str] = []
    for name, block in zip(refined, blocks):
        if counts[name] > 1:
            name += f"_ref{block.reference_number}"
        resolved.append(name)

    counts = Counter(resolved)
    occurrence: Counter[str] = Counter()
    final: list[str] = []
    for name, block in zip(resolved, blocks):
        if counts[name] > 1:
            occurrence[name] += 1
            name += f"_b{block.header_line_number}"
        final.append(name + ".cia")
    return final


def _safe_suffix(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9.-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")
