"""Telemetry module for BrowsePilot — logs discrepancies and tool events to Azure Application Insights."""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("browsepilot.telemetry")

# Application Insights connection string (set via env var or .env)
_CONNECTION_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

# Consent flag — must be explicitly enabled by user at startup
_telemetry_enabled = False

# App Insights exporter (lazy init)
_exporter = None


def is_enabled() -> bool:
    return _telemetry_enabled


def set_consent(enabled: bool) -> None:
    global _telemetry_enabled
    _telemetry_enabled = enabled
    if enabled:
        _init_exporter()


def _init_exporter():
    """Initialize the Azure Monitor exporter if a connection string is available."""
    global _exporter
    if not _CONNECTION_STRING:
        logger.info("No APPLICATIONINSIGHTS_CONNECTION_STRING set — telemetry will log locally only.")
        return
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        _exporter = AzureLogHandler(connection_string=_CONNECTION_STRING)
        logger.addHandler(_exporter)
        logger.setLevel(logging.INFO)
    except Exception as e:
        logger.warning(f"Could not initialize Azure telemetry: {e}")


def log_discrepancy(
    url: str,
    expected: str,
    actual: str,
    user_query: str = "",
    model: str = "",
    category: str = "ui_discrepancy",
) -> dict:
    """Log a UI discrepancy — where the AI expected something but found something different.

    This data can be used by backend teams to:
    - Update stale documentation
    - Improve AI training data
    - Track which portal UIs change most frequently

    Returns the discrepancy record for confirmation.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "discrepancy",
        "category": category,
        "url": url,
        "expected": expected,
        "actual": actual,
        "user_query": user_query,
        "model": model,
    }

    if not _telemetry_enabled:
        return {"status": "telemetry_disabled", "record": record}

    # Log to Azure Application Insights (if configured) and local logger
    properties = {"custom_dimensions": json.dumps(record)}
    logger.info(
        "BrowsePilot Discrepancy: %(category)s at %(url)s",
        {**record},
        extra=properties,
    )

    return {"status": "logged", "record": record}


def log_tool_event(
    tool_name: str,
    url: str = "",
    success: bool = True,
    duration_ms: float = 0,
    model: str = "",
    details: str = "",
) -> None:
    """Log a tool execution event for observability."""
    if not _telemetry_enabled:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "tool_execution",
        "tool_name": tool_name,
        "url": url,
        "success": success,
        "duration_ms": round(duration_ms, 1),
        "model": model,
        "details": details[:500],  # cap detail length
    }

    properties = {"custom_dimensions": json.dumps(record)}
    logger.info(
        "BrowsePilot Tool: %(tool_name)s success=%(success)s",
        record,
        extra=properties,
    )


def log_session_event(
    event_type: str,
    model: str = "",
    browser: str = "",
    details: str = "",
) -> None:
    """Log a session lifecycle event (start, end, error)."""
    if not _telemetry_enabled:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": f"session_{event_type}",
        "model": model,
        "browser": browser,
        "details": details[:500],
    }

    properties = {"custom_dimensions": json.dumps(record)}
    logger.info(
        "BrowsePilot Session: %(event_type)s",
        {"event_type": f"session_{event_type}"},
        extra=properties,
    )
