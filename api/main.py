"""AegisOps API - FastAPI application entry point.

Provides the frontend-facing REST gateway. Aggregates data from the database,
agent processes, and MCP layer. Never exposes secrets or executes commands.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import AegisOpsAuth
from api.errors import error_response
from api.routes import incidents, audit, security, system, services, agents, mcps

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("aegisops.api")


def _structured_log(record: logging.LogRecord) -> dict:
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
        "service": "api",
        "level": record.levelname,
        "message": record.getMessage(),
        "request_id": getattr(record, "request_id", None),
        "incident_id": getattr(record, "incident_id", None),
    }


class ApiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        return json.dumps(_structured_log(record), default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(ApiFormatter())
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


class AppState:
    auth: AegisOpsAuth | None = None
    started_at: float = time.time()


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.auth = AegisOpsAuth()
    logger.info("api_started", extra={"request_id": None, "incident_id": None})
    yield
    logger.info("api_stopped", extra={"request_id": None, "incident_id": None})


app = FastAPI(
    title="AegisOps API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if os.environ.get("APP_ENV") != "production" else None,
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:4173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# ---------------------------------------------------------------------------
# Request ID + error handling
# ---------------------------------------------------------------------------


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request.state.request_id = request_id
    start = time.time()
    try:
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "incident_id": None,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": f"{elapsed:.0f}",
            },
        )
        return response
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        logger.error(
            "request_error",
            extra={
                "request_id": request_id,
                "incident_id": None,
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
                "ms": f"{elapsed:.0f}",
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred.",
                    "request_id": request_id,
                }
            },
        )


# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------

app.include_router(system.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(security.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(mcps.router, prefix="/api")

# Auth routes are mounted in the system router at /api/auth


@app.get("/api")
async def api_root():
    return {
        "service": "AegisOps API",
        "version": app.version,
        "endpoints": [
            "/api/health/live",
            "/api/health/ready",
            "/api/system/status",
            "/api/system/configuration",
            "/api/incidents",
            "/api/incidents/{id}",
            "/api/incidents/{id}/timeline",
            "/api/incidents/{id}/audit",
            "/api/audit",
            "/api/security/authority",
            "/api/agents",
            "/api/services",
            "/api/mcps",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/session",
        ],
    }