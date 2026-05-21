"""tiny_dec package."""

from __future__ import annotations

from typing import Any

__all__ = ["ProgramView", "decompile_function"]


def __getattr__(name: str) -> Any:
    if name == "ProgramView":
        from tiny_dec.loader import ProgramView

        return ProgramView
    if name == "decompile_function":
        from tiny_dec.pipeline import decompile_function

        return decompile_function
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
