"""Turbopuffer client initialization."""

import os
import sys

from turbopuffer import Turbopuffer

from tpuff.utils.debug import debug_log
from tpuff.utils.regions import DEFAULT_REGION

# Global client cache to avoid re-creating clients for the same region
_client_cache: dict[str, Turbopuffer] = {}


def get_turbopuffer_client(region_override: str | None = None) -> Turbopuffer:
    """Get a Turbopuffer client configured with the appropriate region.

    Args:
        region_override: Optional region to use instead of environment variable.

    Returns:
        Configured Turbopuffer client.
    """
    api_key = os.environ.get("TURBOPUFFER_API_KEY")

    if not api_key:
        print("Error: TURBOPUFFER_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)

    # Determine the region
    base_url = os.environ.get("TURBOPUFFER_BASE_URL")
    region = region_override or os.environ.get("TURBOPUFFER_REGION") or DEFAULT_REGION

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
