"""Service monitoring routes."""

from __future__ import annotations

import subprocess

import httpx
from fastapi import APIRouter

router = APIRouter(tags=["services"])


async def _check_auth_api_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:8080/health")
            if resp.status_code < 500:
                return {"status": "online", "http_status": resp.status_code}
            return {"status": "error", "http_status": resp.status_code}
    except httpx.ConnectError:
        return {"status": "offline"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _docker_inspect(container: str) -> dict | None:
    try:
        result = subprocess.run(
            ["docker", "inspect", container],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        import json
        data = json.loads(result.stdout)
        if data:
            return {
                "id": data[0].get("Id", "")[:12],
                "state": data[0].get("State", {}).get("Status", "unknown"),
                "image": data[0].get("Config", {}).get("Image", ""),
                "name": data[0].get("Name", "").lstrip("/"),
            }
    except Exception:
        return None
    return None


@router.get("/services")
async def list_services():
    health = await _check_auth_api_health()
    docker_info = _docker_inspect("auth-api")
    return {
        "services": [
            {
                "name": "auth-api",
                "health": health,
                "docker": docker_info,
            }
        ]
    }