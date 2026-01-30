"""Platform-specific configuration and path resolution.

Uses platformdirs for XDG/macOS-compliant paths with environment variable overrides.

Environment variables:
    PURCHASES_DB_PATH   - Direct path to the SQLite database file
    PURCHASES_DATA_DIR  - Directory for data files (DB goes here if PURCHASES_DB_PATH not set)
    PURCHASES_CONFIG_DIR - Directory for config files (future use)
    VAULT_PATH          - Path to Obsidian vault root
"""

import os
from pathlib import Path

import platformdirs

APP_NAME = "purchases"
APP_AUTHOR = "mroethli"


def get_data_dir() -> Path:
    """Get the data directory, creating it if needed.

    Precedence:
    1. PURCHASES_DATA_DIR environment variable
    2. Platform default (~/Library/Application Support/purchases on macOS,
       ~/.local/share/purchases on Linux)
    """
    env_dir = os.environ.get("PURCHASES_DATA_DIR")
    if env_dir:
        path = Path(env_dir)
    else:
        path = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    """Get the config directory, creating it if needed.

    Precedence:
    1. PURCHASES_CONFIG_DIR environment variable
    2. Platform default (~/Library/Application Support/purchases on macOS,
       ~/.config/purchases on Linux)
    """
    env_dir = os.environ.get("PURCHASES_CONFIG_DIR")
    if env_dir:
        path = Path(env_dir)
    else:
        path = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    """Get the database file path.

    Precedence:
    1. PURCHASES_DB_PATH environment variable (direct path to DB file)
    2. data_dir/purchases.db
    """
    env_path = os.environ.get("PURCHASES_DB_PATH")
    if env_path:
        return Path(env_path)

    return get_data_dir() / "purchases.db"


def get_vault_path() -> Path | None:
    """Get the Obsidian vault path.

    Precedence:
    1. VAULT_PATH environment variable
    2. Default macOS location for Orbis Sapiens vault
    3. None if default doesn't exist
    """
    env_path = os.environ.get("VAULT_PATH")
    if env_path:
        return Path(env_path)

    # Default macOS Obsidian vault location
    default = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Orbis Sapiens"
    if default.exists():
        return default

    return None


def get_resolved_config() -> dict:
    """Get all resolved configuration values for display."""
    vault = get_vault_path()
    return {
        "data_dir": str(get_data_dir()),
        "config_dir": str(get_config_dir()),
        "db_path": str(get_db_path()),
        "db_exists": get_db_path().exists(),
        "vault_path": str(vault) if vault else None,
        "vault_exists": vault.exists() if vault else False,
        "env_overrides": {
            "PURCHASES_DB_PATH": os.environ.get("PURCHASES_DB_PATH"),
            "PURCHASES_DATA_DIR": os.environ.get("PURCHASES_DATA_DIR"),
            "PURCHASES_CONFIG_DIR": os.environ.get("PURCHASES_CONFIG_DIR"),
            "VAULT_PATH": os.environ.get("VAULT_PATH"),
        },
    }
