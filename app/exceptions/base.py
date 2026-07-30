from __future__ import annotations


class ApplicationException(Exception):
    def __init__(self, message: str, detail: str | None = None, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.status_code = status_code


