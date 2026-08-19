"""auth-api - the incident target service for AegisOps.

A deliberately minimal FastAPI service that can be made unhealthy on demand and
recovered by a real container restart. State is in-memory: a Docker restart
naturally resets it to the initial healthy state.

Endpoints:
    GET  /health  -> 200 {"status":"healthy", ...} | 503 {"status":"unhealthy", ...}
    POST /break   -> 200 {"status":"broken"}        (simulate an incident)
    POST /fix     -> 200 {"status":"fixed"}         (application-level recovery)

The eventual AegisOps remediation action (`restart_service("auth-api")`) will
restart this container for real - the reset that clears the broken flag.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="auth-api", version="0.1.0")

_STARTED_AT = time.time()
_broken = False


def _uptime_seconds() -> int:
    return int(time.time() - _STARTED_AT)


@app.get("/")
def root() -> dict:
    return {"service": "auth-api", "version": app.version, "endpoints": ["/health", "/break", "/fix"]}


@app.get("/health")
def health() -> JSONResponse:
    if _broken:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "reason": "simulated_failure",
                "uptime_seconds": _uptime_seconds(),
            },
        )
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "uptime_seconds": _uptime_seconds()},
    )


@app.post("/break")
def break_service() -> dict:
    """Simulate an incident: the service reports unhealthy until recovered."""
    global _broken
    _broken = True
    return {"status": "broken", "detail": "health will report unhealthy until a restart or /fix"}


@app.post("/fix")
def fix_service() -> dict:
    """Application-level recovery. Note: the real remediation path is a container restart."""
    global _broken
    _broken = False
    return {"status": "fixed", "detail": "health reports healthy again"}