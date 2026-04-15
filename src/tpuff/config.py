"""Config management for tpuff environments.

Stores named environments in ~/.tpuff/config.toml with API keys, regions, and base URLs.
"""

import os
import stat
import sys
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".tpuff"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def _read_toml(path: Path) -> dict:
    """Read a TOML file, using tomllib (3.11+) or tomli fallback."""
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config() -> dict:
    """Load config from ~/.tpuff/config.toml. Returns empty dict if not found."""
    if not CONFIG_FILE.exists():
        return {}
    return _read_toml(CONFIG_FILE)


def save_config(config: dict) -> None:
    """Write config to ~/.tpuff/config.toml with secure permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 0o700

    CONFIG_FILE.write_bytes(tomli_w.dumps(config).encode())
    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def get_active_env() -> tuple[str, dict] | None:
    """Return (name, env_dict) for the active environment, or None."""
    config = load_config()
    active = config.get("active")
    if not active:
        return None
    envs = config.get("envs", {})
    if active not in envs:
        return None
    return active, envs[active]


def get_env(name: str) -> dict | None:
    """Get a specific named environment, or None if not found."""
    config = load_config()
    return config.get("envs", {}).get(name)


def list_envs() -> list[tuple[str, dict, bool]]:
    """Return list of (name, env_dict, is_active) for all environments."""
    config = load_config()
    active = config.get("active")
    envs = config.get("envs", {})
    return [(name, env_dict, name == active) for name, env_dict in envs.items()]


def add_env(name: str, api_key: str, region: str, base_url: str = "") -> None:
    """Add or overwrite an environment."""
    config = load_config()
    if "envs" not in config:
        config["envs"] = {}
    env = {"api_key": api_key, "region": region}
    if base_url:
        env["base_url"] = base_url
    config["envs"][name] = env
    # Set as active if it's the first env
    if "active" not in config or not config["active"]:
        config["active"] = name
    save_config(config)


def remove_env(name: str) -> None:
    """Remove an environment. Errors if not found."""
    config = load_config()
    envs = config.get("envs", {})
    if name not in envs:
        print(f"Error: environment '{name}' not found", file=sys.stderr)
        sys.exit(1)
    del envs[name]
    # If we removed the active env, clear it or pick another
    if config.get("active") == name:
        if envs:
            config["active"] = next(iter(envs))
        else:
            config["active"] = ""
    save_config(config)


def set_active(name: str) -> None:
    """Set the active environment."""
    config = load_config()
    envs = config.get("envs", {})
    if name not in envs:
        print(f"Error: environment '{name}' not found", file=sys.stderr)
        sys.exit(1)
    config["active"] = name
    save_config(config)


def deletes_allowed() -> bool:
    """Check if deletes are allowed. Defaults to False."""
    config = load_config()
    return config.get("allow_deletes", False)
