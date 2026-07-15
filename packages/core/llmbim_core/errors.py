"""Structured errors recoverable by LLM agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BimError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(BimError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("NOT_FOUND", message, details)


class ValidationError(BimError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("VALIDATION_FAILED", message, details)


class HostNotFoundError(BimError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("HOST_NOT_FOUND", message, details)


class GeometryDegenerateError(BimError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("GEOMETRY_DEGENERATE", message, details)


class NotImplementedBimError(BimError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("NOT_IMPLEMENTED", message, details)
