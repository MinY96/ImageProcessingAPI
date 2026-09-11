from __future__ import annotations

from typing import Any


class ApiRequestError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "details": self.details,
            }
        }
