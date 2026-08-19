"""AegisOps ArmorIQ integration package (client + identity foundation)."""

from .client_setup import (
    KEYS_DIR,
    PROJECT_ROOT,
    generate_and_save_keypair,
    get_api_key,
    get_client,
    keypair_paths,
    load_env,
    load_private_key,
    public_key_hex,
    save_keypair,
)

__all__ = [
    "KEYS_DIR",
    "PROJECT_ROOT",
    "generate_and_save_keypair",
    "get_api_key",
    "get_client",
    "keypair_paths",
    "load_env",
    "load_private_key",
    "public_key_hex",
    "save_keypair",
]