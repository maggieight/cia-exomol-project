from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

BUILD_TIMEZONE = "Europe/London"
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class BuildContext:
    build_date: date
    timezone: str = BUILD_TIMEZONE

    @property
    def version(self) -> str:
        return self.build_date.strftime("%Y%m%d")

    @classmethod
    def capture(cls, clock: Clock | None = None) -> "BuildContext":
        timezone = ZoneInfo(BUILD_TIMEZONE)
        instant = clock() if clock is not None else datetime.now(timezone)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone)
        return cls(build_date=instant.astimezone(timezone).date())

    @classmethod
    def from_date(cls, build_date: date) -> "BuildContext":
        return cls(build_date=build_date)
