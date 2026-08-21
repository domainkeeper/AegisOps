"""AegisOps API authentication — HMAC-signed bearer tokens.

Separate from ArmorIQ authorization. Uses env vars:
  AEGISOPS_API_USERNAME     (default: "admin")
  AEGISOPS_API_PASSWORD     (plaintext password)
  AEGISOPS_API_SECRET_KEY   (HMAC signing key)
  APP_ENV                   (default: "development")

In production (APP_ENV=production) authentication is REQUIRED.
In development, missing credentials are warned and access is allowed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets

__all__: list[str] = [
    "AegisOpsAuth",
    "create_token",
    "verify_token",
]

TOKEN_DELIMITER = "."

logger = logging.getLogger("aegisops.api.auth")


# ---------------------------------------------------------------------------
# Standalone helpers (also usable outside the class)
# ---------------------------------------------------------------------------

def _sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def create_token(username: str, secret: str) -> str:
    """Return an HMAC-signed bearer token for *username*."""
    payload = base64.b64encode(username.encode()).decode()
    sig = _sign(secret, payload)
    return f"{payload}{TOKEN_DELIMITER}{sig}"


def verify_token(token: str, secret: str) -> str | None:
    """If *token* is valid return the embedded username, else ``None``."""
    try:
        payload, sig = token.split(TOKEN_DELIMITER, maxsplit=1)
        expected = _sign(secret, payload)
        if hmac.compare_digest(sig, expected):
            return base64.b64decode(payload.encode()).decode()
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Class-based wrapper
# ---------------------------------------------------------------------------

class AegisOpsAuth:
    """Configurable authenticator for the AegisOps API."""

    def __init__(self) -> None:
        self.username: str = os.environ.get("AEGISOPS_API_USERNAME", "admin")
        self.password: str | None = os.environ.get("AEGISOPS_API_PASSWORD", None)
        self.secret_key: str = os.environ.get("AEGISOPS_API_SECRET_KEY", "")
        self.app_env: str = os.environ.get("APP_ENV", "development")
        self._is_production = self.app_env == "production"

        # Guard: production requires a secret key
        if not self.secret_key:
            if self._is_production:
                raise RuntimeError(
                    "AEGISOPS_API_SECRET_KEY must be set when APP_ENV=production"
                )
            self.secret_key = secrets.token_hex(32)
            logger.warning(
                "AEGISOPS_API_SECRET_KEY not set — generated ephemeral key for development. "
                "Set a persistent key for production."
            )

        # Production mode requires a password
        if self._is_production and not self.password:
            raise RuntimeError(
                "AEGISOPS_API_PASSWORD must be set when APP_ENV=production"
            )

        if not self.password:
            logger.warning(
                "AEGISOPS_API_PASSWORD not set — unauthenticated access allowed in development mode."
            )

    def login(self, username: str, password: str) -> str | None:
        """Return a signed token if credentials match, else ``None``."""
        if username != self.username:
            return None
        if self.password is not None:
            if not hmac.compare_digest(password, self.password):
                return None
        elif self._is_production:
            return None  # production requires a password
        return create_token(username, self.secret_key)

    def verify(self, token: str | None) -> bool:
        """Return ``True`` if *token* is a valid bearer token."""
        if token is None:
            return False
        return verify_token(token, self.secret_key) is not None

    def create_token(self, username: str) -> str:
        """Create an HMAC-signed bearer token for *username*."""
        return create_token(username, self.secret_key)

    @property
    def is_authenticated(self) -> bool:
        """``True`` when authentication is enforced (production + credentials configured)."""
        return self._is_production and self.password is not None