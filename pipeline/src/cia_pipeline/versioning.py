"""check whether all version are in valid format"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

VERSION_RE = re.compile(r"^\d{8}$")


def is_valid_version(value: Any) -> bool:
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


def validate_version(value: Any, field: str = "version") -> None:
    if not is_valid_version(value):
        raise ValueError(f"{field} must be a valid YYYYMMDD string")
