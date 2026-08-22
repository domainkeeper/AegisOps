"""System-level routes: health, auth, SSE events."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from api.auth import AegisOpsAuth, verify_token
from api.errors import error_response
from database.audit import get_store

logger = logging.getLogger("aegisops.api.routes.system")
_started_at = time.time()

router = APIRouter(tags=["system"])


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


async def get_current_user(authorization: str | None = Header(None)):
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    auth = AegisOpsAuth()
    return verify_token(token, auth.secret_key)


async def require_auth(user: str | None = Depends(get_current_user)):
    auth = AegisOpsAuth()
    if not auth.is_authenticated:
        return "development"
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required",
                    "request_id": "",
                }
            },
        )
    return user


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health/live")
async def health_live():
    return {"status": "alive", "uptime_seconds": int(time.time() - _started_at)}


@router.get("/health/ready")
async def health_ready():
    try:
        store = get_store()
        with store._lock:
            store._conn.execute("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.warning("health/ready check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "error", "detail": str(exc)},
        )


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------


async def _async_probe(url: str, timeout: float = 2.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        if resp.status_code < 500:
            return "online"
        return "error"
    except httpx.RequestError:
        return "offline"
    except Exception as exc:
        return f"error: {exc}"


@router.get("/system/status")
async def system_status():
    try:
        async def probe_agent(name: str, url: str) -> tuple[str, str]:
            return name, await _async_probe(url, timeout=2.0)

        async def probe_mcp(name: str, url: str) -> tuple[str, str]:
            return name, await _async_probe(url, timeout=2.0)

        # Run all probes concurrently
        agent_probes = [
            probe_agent("log_agent", "http://log-agent:8091/health"),
            probe_agent("diagnosis_agent", "http://diagnosis-agent:8092/health"),
            probe_agent("remediation_agent", "http://remediation-agent:8093/health"),
            probe_agent("commander", "http://commander:8094/health"),
        ]
        mcp_probes = [
            probe_mcp("log_mcp", "http://log-mcp:8081/mcp"),
            probe_mcp("diagnostic_mcp", "http://diagnostic-mcp:8082/mcp"),
            probe_mcp("remediation_mcp", "http://remediation-mcp:8083/mcp"),
        ]

        agent_results = await asyncio.gather(*agent_probes, return_exceptions=True)
        mcp_results = await asyncio.gather(*mcp_probes, return_exceptions=True)

        agents = {}
        for result in agent_results:
            if isinstance(result, Exception):
                logger.warning(f"Agent probe failed: {result}")
                continue
            name, status = result
            agents[name] = status

        mcps = {}
        for result in mcp_results:
            if isinstance(result, Exception):
                logger.warning(f"MCP probe failed: {result}")
                continue
            name, status = result
            mcps[name] = status

        armoriq = {"configured": bool(os.environ.get("ARMORIQ_API_KEY", "").strip())}
        gemini = {"configured": bool(os.environ.get("AEGISOPS_GEMINI_API_KEY", "").strip())}
        auth_api_status = await _async_probe("http://auth-api:8080/health", timeout=2.0)
        docker_auth = await _async_probe("http://auth-api:8080/health", timeout=2.0)
        auth_api = {
            "http": auth_api_status,
            "docker": docker_auth,
        }
        return {
            "agents": agents,
            "mcps": mcps,
            "armoriq": armoriq,
            "gemini": gemini,
            "auth_api": auth_api,
            "uptime_seconds": time.time() - _started_at,
        }
    except Exception as exc:
        logger.exception("system_status failed")
        # Return a graceful degraded response instead of 500
        return {
            "agents": {},
            "mcps": {},
            "armoriq": {"configured": bool(os.environ.get("ARMORIQ_API_KEY", "").strip())},
            "gemini": {"configured": bool(os.environ.get("AEGISOPS_GEMINI_API_KEY", "").strip())},
            "auth_api": {"http": "error", "docker": "error"},
            "uptime_seconds": time.time() - _started_at,
        }


@router.get("/system/configuration")
async def system_configuration():
    from armoriq.plan import PLAN_ACTIONS, PLAN_LLM_LABEL, armoriq_configured

    return {
        "armoriq": {"configured": armoriq_configured()},
        "gemini": {"configured": bool(os.environ.get("AEGISOPS_GEMINI_API_KEY", "").strip())},
        "plan": {"actions": list(PLAN_ACTIONS), "llm_label": PLAN_LLM_LABEL},
        "auth": {
            "enforced": bool(os.environ.get("APP_ENV") == "production"),
        },
        "cors_origins": os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:4173,http://localhost:3000",
        ).split(","),
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@router.post("/auth/login")
async def auth_login(body: dict):
    username = body.get("username", "")
    password = body.get("password", "")
    auth = AegisOpsAuth()
    token = auth.login(username, password)
    if token is None:
        return error_response(
            code="INVALID_CREDENTIALS",
            message="Invalid username or password",
            status=401,
        )
    return {"token": token, "username": username}


@router.get("/auth/session")
async def auth_session(user: str | None = Depends(get_current_user)):
    auth = AegisOpsAuth()
    if user is None and auth.is_authenticated:
        return {"authenticated": False, "username": ""}
    if user is None:
        return {"authenticated": True, "username": "development", "mode": "development"}
    return {"authenticated": True, "username": user}


@router.post("/auth/logout")
async def auth_logout():
    return {"status": "logged_out"}


# ---------------------------------------------------------------------------
# Server-Sent Events
# ---------------------------------------------------------------------------


async def event_stream():
    last_id = 0
    while True:
        store = get_store()
        with store._lock:
            rows = store._conn.execute(
                "SELECT id, incident_id, agent, action, status, created_at "
                "FROM audit_events WHERE id > ? ORDER BY id ASC",
                (last_id,),
            ).fetchall()
        for row in rows:
            last_id = row[0]
            data = json.dumps(
                {
                    "id": row[0],
                    "incident_id": row[1],
                    "agent": row[2],
                    "action": row[3],
                    "status": row[4],
                    "created_at": row[5],
                }
            )
            yield f"data: {data}\n\n"
        await asyncio.sleep(2)


@router.get("/events")
async def events():
    return StreamingResponse(
        event_stream(), media_type="text/event-stream"
    )