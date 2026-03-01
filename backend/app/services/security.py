from __future__ import annotations

"""
Security and abuse prevention.

Even though agents are configured (not arbitrary code), treat them as adversarial:
  - Action channel is strict JSON only — no free-form text
  - Schema validation on every action
  - Timeouts on inference calls
  - Rate limits on API endpoints
  - Hard caps on memory growth
  - Engine is fully isolated — models never mutate engine state

This module provides validation helpers and rate-limit tracking.
"""

import time
from datetime import datetime, timezone

ACTION_SCHEMA = {
    "required_fields": {"action_type"},
    "valid_action_types": {"fold", "check", "call", "raise", "all_in"},
    "optional_fields": {"amount", "confidence", "rationale_id"},
}

INFERENCE_TIMEOUT_MS = 30000
MAX_MEMORY_CHARS_PER_AGENT = 8000
MAX_ACTIONS_PER_MINUTE = 30

_rate_limits: dict[str, list[float]] = {}


def validate_action_schema(action: dict) -> tuple[bool, str]:
    """Strictly validate action JSON against the fixed schema."""
    if not isinstance(action, dict):
        return False, "Action must be a JSON object."

    action_type = action.get("action_type") or action.get("type") or action.get("action")
    if not action_type:
        return False, "Missing required field: 'action_type', 'type', or 'action'."

    if action_type.lower() not in ACTION_SCHEMA["valid_action_types"]:
        return False, f"Invalid action_type '{action_type}'. Valid: {ACTION_SCHEMA['valid_action_types']}"

    if action_type.lower() in ("raise", "all_in"):
        amount = action.get("amount")
        if amount is not None:
            try:
                int(amount)
            except (ValueError, TypeError):
                return False, f"'amount' must be an integer, got '{amount}'."

    # Reject unexpected keys, but allow internal orchestrator metadata
    allowed_keys = {"action_type", "type", "amount", "confidence", "rationale_id",
                    "action", "reasoning", "parse_ok", "raw", "memory_update",
                    "table_talk"}
    unexpected = set(action.keys()) - allowed_keys
    if unexpected:
        return False, f"Unexpected fields in action: {unexpected}. Only strict JSON allowed."

    return True, ""


def check_rate_limit(agent_id: str) -> tuple[bool, str]:
    """Returns (allowed, error_message)."""
    now = time.monotonic()
    if agent_id not in _rate_limits:
        _rate_limits[agent_id] = []

    window = _rate_limits[agent_id]
    # Prune entries older than 60 seconds
    _rate_limits[agent_id] = [t for t in window if now - t < 60]
    window = _rate_limits[agent_id]

    if len(window) >= MAX_ACTIONS_PER_MINUTE:
        return False, f"Rate limit exceeded: {MAX_ACTIONS_PER_MINUTE} actions/minute."

    window.append(now)
    return True, ""


def check_memory_budget(current_chars: int) -> tuple[bool, str]:
    if current_chars > MAX_MEMORY_CHARS_PER_AGENT:
        return False, f"Memory budget exceeded: {current_chars}/{MAX_MEMORY_CHARS_PER_AGENT} chars."
    return True, ""


def sanitize_response(raw: str, max_length: int = 2000) -> str:
    """Truncate and clean raw LLM response to prevent abuse."""
    if len(raw) > max_length:
        raw = raw[:max_length] + "...[truncated]"
    return raw
