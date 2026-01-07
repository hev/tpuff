"""Debug logging utilities for tpuff CLI."""

import json
import os
from typing import Any

from rich.console import Console

# Console for debug output
console = Console(stderr=True)

# Global debug state - set via --debug flag or DEBUG env var
_debug_enabled = False


def enable_debug() -> None:
    """Enable debug logging."""
    global _debug_enabled
    _debug_enabled = True


def is_debug_enabled() -> bool:
    """Check if debug is enabled."""
    return _debug_enabled or os.environ.get("DEBUG") in ("true", "1")


def filter_vectors(obj: Any) -> Any:
    """Recursively filters out vector arrays from objects to make debug logs more readable."""
    if obj is None:
        return obj

    # If it's a list with all numbers and length > 10, it's likely a vector
    if isinstance(obj, list):
        if len(obj) > 10 and all(isinstance(item, (int, float)) for item in obj):
            return f"[vector with {len(obj)} dimensions]"
        return [filter_vectors(item) for item in obj]

    # If it's a dict, recursively filter its properties
    if isinstance(obj, dict):
        filtered = {}
        for key, value in obj.items():
            # Skip keys named 'vector' or attributes that are large number arrays
            if key == "vector" and isinstance(value, list) and len(value) > 10:
                filtered[key] = f"[vector with {len(value)} dimensions]"
            else:
                filtered[key] = filter_vectors(value)
        return filtered

    return obj


def debug_log(label: str, data: Any) -> None:
    """Log debug information (only shown when debug is enabled)."""
    if is_debug_enabled():
        console.print(f"\n[dim][DEBUG] {label}:[/dim]")
        filtered = filter_vectors(data)
        if isinstance(filtered, str):
            console.print(f"[dim]{filtered}[/dim]")
        else:
            console.print(f"[dim]{json.dumps(filtered, indent=2, default=str)}[/dim]")


def debug_request(method: str, url: str, payload: Any = None) -> None:
    """Log raw API request."""
    if is_debug_enabled():
        console.print("\n[dim][DEBUG] API Request:[/dim]")
        console.print(f"[dim]  Method: {method}[/dim]")
        console.print(f"[dim]  URL: {url}[/dim]")
        if payload:
            console.print("[dim]  Payload:[/dim]")
            payload_str = json.dumps(payload, indent=2, default=str)
            for line in payload_str.split("\n"):
                console.print(f"[dim]  {line}[/dim]")


def debug_response(status: int, data: Any) -> None:
    """Log raw API response."""
    if is_debug_enabled():
        console.print("\n[dim][DEBUG] API Response:[/dim]")
        console.print(f"[dim]  Status: {status}[/dim]")
        console.print("[dim]  Data:[/dim]")
        data_str = json.dumps(data, indent=2, default=str)
        for line in data_str.split("\n"):
            console.print(f"[dim]  {line}[/dim]")
