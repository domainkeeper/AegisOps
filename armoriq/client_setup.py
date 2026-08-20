"""ArmorIQ client and identity foundation for AegisOps.

Phase 1 scope: establish the mechanism only. No agent logic lives here.
Phase 5 scope: per-agent identity lifecycle — each agent process loads env,
ensures its own Ed25519 keypair (.keys/<agent>/), resolves its own email scope,
and builds its own ArmorIQClient.

Identity model (verified against armoriq-sdk 0.6.10, docs.armoriq.ai):
one API key + per-request `for_user(email)` scopes. Agent identity therefore =
separate process + separate keypair + per-agent email. `user_id`/`agent_id`
are deprecated in the current SDK and NOT used.

Security rules (ARCHITECTURE.md §Security):
- Private keys live only in .keys/ (gitignored). Never logged, never sent over
  HTTP, never returned by any endpoint. Only the hex public key may be shared.
"""

from __future__ import annotations

import os
from pathlib import Path

from armoriq_sdk import ArmorIQClient, ConfigurationException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KEYS_DIR = PROJECT_ROOT / ".keys"

VALID_KEY_PREFIXES = ("ak_live_", "ak_test_", "ak_claw_")

# The four agent roles. The email env vars let an operator override the
# PLAN §5 convention (<role>@aegisops.local) per deployment.
AGENT_EMAIL_ENV: dict[str, str] = {
    "commander": "AEGISOPS_COMMANDER_EMAIL",
    "log_agent": "AEGISOPS_LOG_AGENT_EMAIL",
    "diagnosis_agent": "AEGISOPS_DIAGNOSIS_AGENT_EMAIL",
    "remediation_agent": "AEGISOPS_REMEDIATION_AGENT_EMAIL",
}

AGENT_ROLES = tuple(AGENT_EMAIL_ENV)


def load_env() -> None:
    """Load .env from the project root if present (optional; env vars always win)."""
    load_dotenv(PROJECT_ROOT / ".env")


def get_api_key() -> str:
    """Return the ArmorIQ API key, raising a clear ConfigurationException if missing."""
    load_env()
    key = os.environ.get("ARMORIQ_API_KEY", "").strip()
    if not key:
        raise ConfigurationException(
            "ARMORIQ_API_KEY is not set. Copy .env.example to .env and set it, "
            "or run `armoriq login` to write ~/.armoriq/credentials.json."
        )
    if not key.startswith(VALID_KEY_PREFIXES):
        raise ConfigurationException(
            f"ARMORIQ_API_KEY looks malformed: must start with {VALID_KEY_PREFIXES} "
            f"(got {key[:12]}...). Get a key from the ArmorIQ dashboard."
        )
    return key


def get_client() -> ArmorIQClient:
    """Build a client from environment configuration. One client per process."""
    load_env()
    use_production = os.environ.get("USE_PRODUCTION", "true").strip().lower() != "false"
    return ArmorIQClient(
        api_key=get_api_key(),
        use_production=use_production,
        iap_endpoint=os.environ.get("IAP_ENDPOINT") or None,
        proxy_endpoint=os.environ.get("PROXY_ENDPOINT") or None,
        backend_endpoint=os.environ.get("BACKEND_ENDPOINT") or None,
    )


def agent_email(agent: str) -> str:
    """Per-agent email scope for `for_user(email)` / `user_email=...`.

    Reads AEGISOPS_<ROLE>_EMAIL from the environment; falls back to the
    PLAN §5 convention `<role>@aegisops.local`. Never an ArmorIQ credential.
    """
    if agent not in AGENT_EMAIL_ENV:
        raise ConfigurationException(
            f"unknown agent role '{agent}'; expected one of: {AGENT_ROLES}"
        )
    load_env()
    return os.environ.get(AGENT_EMAIL_ENV[agent], f"{agent}@aegisops.local").strip()


# ---------------------------------------------------------------------------
# Ed25519 identity (delegation binding) lifecycle
# ---------------------------------------------------------------------------


def keypair_paths(agent: str) -> tuple[Path, Path]:
    """(private_key_path, public_key_hex_path) for an agent, under .keys/<agent>/.

    .keys/ is gitignored — private keys are never committed.
    """
    agent_dir = KEYS_DIR / agent
    return agent_dir / "private.pem", agent_dir / "public.hex"


def public_key_hex(private_key: ed25519.Ed25519PrivateKey) -> str:
    """Raw-bytes hex encoding of the public key — the format delegate() expects."""
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def save_keypair(private_key: ed25519.Ed25519PrivateKey, agent: str) -> None:
    """Persist an agent's keypair as PEM (private) + hex (public)."""
    priv_path, pub_path = keypair_paths(agent)
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_bytes = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_bytes)
    pub_path.write_text(public_key_hex(private_key) + "\n")


def load_private_key(agent: str) -> ed25519.Ed25519PrivateKey:
    """Load an agent's private key. Raises FileNotFoundError if it does not exist."""
    priv_path, _ = keypair_paths(agent)
    if not priv_path.exists():
        raise FileNotFoundError(
            f"No keypair for agent '{agent}' ({priv_path}). "
            f"Generate one with ensure_keypair('{agent}')."
        )
    return serialization.load_pem_private_key(priv_path.read_bytes(), password=None)


def generate_and_save_keypair(agent: str) -> ed25519.Ed25519PrivateKey:
    """Generate a fresh Ed25519 keypair for an agent and persist it."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    save_keypair(private_key, agent)
    return private_key


def ensure_keypair(agent: str) -> ed25519.Ed25519PrivateKey:
    """Idempotent keypair lifecycle: load if present, otherwise generate + save."""
    if not keypair_paths(agent)[0].exists():
        return generate_and_save_keypair(agent)
    return load_private_key(agent)