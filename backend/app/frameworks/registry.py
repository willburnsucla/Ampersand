"""FrameworkRegistry: name to Framework lookup.

The set of frameworks lives here in one place, DEFAULT_REGISTRY. Adding one is a
new framework class plus an entry.
"""
from __future__ import annotations

from app.frameworks.base import Framework
from app.frameworks.papalampidi import PapalampidiFramework
from app.frameworks.vonnegut import VonnegutFramework


class FrameworkRegistry:
    def __init__(self, frameworks: list[Framework]) -> None:
        self._by_name: dict[str, Framework] = {f.name: f for f in frameworks}

    def get(self, name: str) -> Framework:
        try:
            return self._by_name[name]
        except KeyError:
            raise ValueError(
                f"unknown framework {name!r}; known: {self.names()}"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def all(self) -> list[Framework]:
        return list(self._by_name.values())


DEFAULT_REGISTRY = FrameworkRegistry([VonnegutFramework(), PapalampidiFramework()])
