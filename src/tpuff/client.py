"""Turbopuffer client initialization."""

import os
import sys

import click
from turbopuffer import Turbopuffer

from tpuff.config import get_active_env, get_env
from tpuff.utils.debug import debug_log
from tpuff.utils.regions import DEFAULT_REGION

# Global client cache to avoid re-creating clients for the same region
_client_cache: dict[str, Turbopuffer] = {}


def _resolve_config(env_name: str | None = None) -> tuple[str | None, str | None, str | None]:
    """Resolve api_key, region, base_url from config file.

    Args:
        env_name: Optional specific environment name to use.

    Returns:
        (api_key, region, base_url) from config, any may be None.
    """
    if env_name:
        env_dict = get_env(env_name)
        if not env_dict:
            print(f"Error: environment '{env_name}' not found in config", file=sys.stderr)
            print("Run 'tpuff env list' to see available environments.", file=sys.stderr)
            sys.exit(1)
        return env_dict.get("api_key"), env_dict.get("region"), env_dict.get("base_url")

    active = get_active_env()
    if active:
        _, env_dict = active
        return env_dict.get("api_key"), env_dict.get("region"), env_dict.get("base_url")

    return None, None, None


def get_turbopuffer_client(region_override: str | None = None) -> Turbopuffer:
    """Get a Turbopuffer client configured with the appropriate region.

    Resolution order:
    1. Environment variables (always win if set)
    2. Config file (~/.tpuff/config.toml) active or --env specified environment
    3. Error with helpful message

    Args:
        region_override: Optional region to use instead of environment variable.

    Returns:
        Configured Turbopuffer client.
    """
    # Get --env flag from Click context if available
    env_name = None
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj:
        env_name = ctx.obj.get("env")

    # Resolve from config file
    cfg_api_key, cfg_region, cfg_base_url = _resolve_config(env_name)

    # Environment variables take priority, then config
    api_key = os.environ.get("TURBOPUFFER_API_KEY") or cfg_api_key

    if not api_key:
        print(
            "Error: No API key found. Set TURBOPUFFER_API_KEY or run 'tpuff env add <name>'.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine the region and base_url
    base_url = os.environ.get("TURBOPUFFER_BASE_URL") or cfg_base_url or None
    region = region_override or os.environ.get("TURBOPUFFER_REGION") or cfg_region or DEFAULT_REGION

    # Cache key is the region or base_url
    cache_key = base_url or region

    if cache_key in _client_cache:
        return _client_cache[cache_key]

    # Create the client
    if base_url:
        client = Turbopuffer(api_key=api_key, base_url=base_url)
        debug_log("Turbopuffer Client Configuration", {
            "base_url": base_url,
            "api_key_present": bool(api_key)
        })
    else:
        client = Turbopuffer(api_key=api_key, region=region)
        debug_log("Turbopuffer Client Configuration", {
            "region": region,
            "api_key_present": bool(api_key)
        })

    _client_cache[cache_key] = client
    return client


def get_namespace(name: str, region_override: str | None = None):
    """Get a Turbopuffer namespace.

    Args:
        name: The namespace name.
        region_override: Optional region to use instead of environment variable.

    Returns:
        Configured Turbopuffer namespace.
    """
    client = get_turbopuffer_client(region_override)
    return client.namespace(name)


def clear_client_cache() -> None:
    """Clear the client cache. Useful when switching regions."""
    global _client_cache
    _client_cache = {}
