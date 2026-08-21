"""Agent status routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["agents"])

AGENT_PORTS = {
    "log_agent": 8091,
    "diagnosis_agent": 8092,
    "remediation_agent": 8093,
    "commander": 8094,
}


async def _probe(port: int) -> dict:
    url = f"http://127.0.0.1:{port}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        if resp.status_code < 500:
            return {"status": "online", "http_status": resp.status_code}
        return {"status": "error", "http_status": resp.status_code}
    except httpx.ConnectError:
        return {"status": "offline"}
    except httpx.TimeoutException:
        return {"status": "timeout"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/agents")
async def list_agents():
    results = {}
    for name, port in AGENT_PORTS.items():
        results[name] = await _probe(port)
    return {"agents": results}