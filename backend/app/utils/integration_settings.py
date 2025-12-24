"""Shared helpers for integration preference payloads."""

from __future__ import annotations

from typing import Any, Dict

DEFAULT_INTEGRATION_SETTINGS: Dict[str, Dict[str, bool]] = {
    "mcp": {
        "bicep": False,
        "terraform": False,
        "docs": False,
    },
    "agents": {
        "architect": True,  # Always enabled
        "security": False,
        "reliability": False,
        "cost": False,
        "networking": False,
        "observability": False,
        "dataStorage": False,
        "compliance": False,
        "identity": False,
        "naming": False,
    }
}


def normalize_integration_settings(payload: Any) -> Dict[str, Dict[str, bool]]:
    """
    Normalize integration preferences from untrusted payloads.

    Ensures all known flags exist and default to False when unspecified.
    """
    normalized = {
        "mcp": {
            "bicep": DEFAULT_INTEGRATION_SETTINGS["mcp"]["bicep"],
            "terraform": DEFAULT_INTEGRATION_SETTINGS["mcp"]["terraform"],
            "docs": DEFAULT_INTEGRATION_SETTINGS["mcp"]["docs"],
        },
        "agents": {
            "architect": DEFAULT_INTEGRATION_SETTINGS["agents"]["architect"],
            "security": DEFAULT_INTEGRATION_SETTINGS["agents"]["security"],
            "reliability": DEFAULT_INTEGRATION_SETTINGS["agents"]["reliability"],
            "cost": DEFAULT_INTEGRATION_SETTINGS["agents"]["cost"],
            "networking": DEFAULT_INTEGRATION_SETTINGS["agents"]["networking"],
            "observability": DEFAULT_INTEGRATION_SETTINGS["agents"]["observability"],
            "dataStorage": DEFAULT_INTEGRATION_SETTINGS["agents"]["dataStorage"],
            "compliance": DEFAULT_INTEGRATION_SETTINGS["agents"]["compliance"],
            "identity": DEFAULT_INTEGRATION_SETTINGS["agents"]["identity"],
            "naming": DEFAULT_INTEGRATION_SETTINGS["agents"]["naming"],
        }
    }
    if not isinstance(payload, dict):
        return normalized

    mcp_settings = payload.get("mcp")
    if isinstance(mcp_settings, dict):
        for key in ("bicep", "terraform", "docs"):
            if key in mcp_settings:
                normalized["mcp"][key] = bool(mcp_settings[key])

    agent_settings = payload.get("agents")
    if isinstance(agent_settings, dict):
        for key in ("architect", "security", "reliability", "cost", "networking", 
                    "observability", "dataStorage", "compliance", "identity", "naming"):
            if key in agent_settings:
                # Architect is always enabled
                if key == "architect":
                    normalized["agents"][key] = True
                else:
                    normalized["agents"][key] = bool(agent_settings[key])

    return normalized
