"""Shared API error utilities — no circular imports (no route imports here)."""

from __future__ import annotations

from fastapi.responses import JSONResponse


def error_response(code: str, message: str, request_id: str | None = None, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id or ""}},
    )