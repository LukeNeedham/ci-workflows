"""A violation of a rule, with where it is."""

from dataclasses import dataclass
from pathlib import PurePath


@dataclass
class Violation:
    path: str
    line: int
    rule: str
    message: str
    anchor: int = 0  # the first line a lint:ignore may sit above

    def __post_init__(self):
        if isinstance(self.path, PurePath):
            self.path = self.path.as_posix()
        self.anchor = self.anchor or self.line
