"""MCP status routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["mcps"])

MCP_PORTS = {
    "log_mcp": 8081,
    "diagnostic_mcp": 8082,
    "remediation_mcp": 8083,
}


async def _probe(port: int) -> dict:
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        if resp.status_code < 500:
            return {"status": "reachable", "http_status": resp.status_code}
        return {"status": "error", "http_status": resp.status_code}
    except httpx.ConnectError:
        return {"status": "unreachable"}
    except httpx.TimeoutException:
        return {"status": "timeout"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/mcps")
async def list_mcps():
    results = {}
    for name, port in MCP_PORTS.items():
        results[name] = await _probe(port)
    return {"mcps": results}