from __future__ import annotations

"""
Decision logging, timing metrics, and failure tracking.

Logs:
  - Every agent decision: action JSON, explanation, memory update artifacts
  - Timing: engine→orchestrator latency, orchestrator→modal inference time
  - Failures: invalid JSON, illegal actions, timeouts

Supports replay: given logs + seed, the engine can replay deterministically.
"""

import time
from datetime import datetime, timezone

_decision_logs: list[dict] = []
_failure_logs: list[dict] = []
_timing_logs: list[dict] = []


class Timer:
    """Context manager for timing operations."""

    def __init__(self):
        self.start_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.monotonic() - self.start_time) * 1000


def log_decision(
    agent_id: str,
    game_id: str,
    hand_id: str,
    action: dict,
    reasoning: str,
    memory_update: str | None,
    inference_latency_ms: float,
    parse_ok: bool,
) -> dict:
    entry = {
        "type": "decision",
        "agent_id": agent_id,
        "game_id": game_id,
        "hand_id": hand_id,
        "action": action,
        "reasoning": reasoning,
        "memory_update": memory_update,
        "inference_latency_ms": round(inference_latency_ms, 1),
        "parse_ok": parse_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _decision_logs.append(entry)
    return entry


def log_failure(
    agent_id: str,
    game_id: str,
    hand_id: str,
    failure_type: str,
    details: str,
    raw_response: str | None = None,
) -> dict:
    """failure_type: 'invalid_json', 'illegal_action', 'timeout', 'error'."""
    entry = {
        "type": "failure",
        "agent_id": agent_id,
        "game_id": game_id,
        "hand_id": hand_id,
        "failure_type": failure_type,
        "details": details,
        "raw_response": raw_response[:500] if raw_response else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _failure_logs.append(entry)
    return entry


def log_timing(
    game_id: str,
    hand_id: str,
    agent_id: str,
    phase: str,
    engine_to_orch_ms: float,
    orch_to_modal_ms: float,
    total_turn_ms: float,
) -> dict:
    entry = {
        "type": "timing",
        "game_id": game_id,
        "hand_id": hand_id,
        "agent_id": agent_id,
        "phase": phase,
        "engine_to_orch_ms": round(engine_to_orch_ms, 1),
        "orch_to_modal_ms": round(orch_to_modal_ms, 1),
        "total_turn_ms": round(total_turn_ms, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _timing_logs.append(entry)
    return entry


# ── Queries ─────────────────────────────────────────────────────────────────

def get_decisions(game_id: str | None = None, agent_id: str | None = None,
                  limit: int = 100) -> list[dict]:
    logs = _decision_logs
    if game_id:
        logs = [l for l in logs if l["game_id"] == game_id]
    if agent_id:
        logs = [l for l in logs if l["agent_id"] == agent_id]
    return list(reversed(logs))[:limit]


def get_failures(game_id: str | None = None, limit: int = 100) -> list[dict]:
    logs = _failure_logs
    if game_id:
        logs = [l for l in logs if l["game_id"] == game_id]
    return list(reversed(logs))[:limit]


def get_timings(game_id: str | None = None, limit: int = 100) -> list[dict]:
    logs = _timing_logs
    if game_id:
        logs = [l for l in logs if l["game_id"] == game_id]
    return list(reversed(logs))[:limit]


def get_game_stats(game_id: str) -> dict:
    decisions = [l for l in _decision_logs if l["game_id"] == game_id]
    failures = [l for l in _failure_logs if l["game_id"] == game_id]
    timings = [l for l in _timing_logs if l["game_id"] == game_id]
    avg_inference = 0.0
    if timings:
        avg_inference = sum(t["orch_to_modal_ms"] for t in timings) / len(timings)
    return {
        "game_id": game_id,
        "total_decisions": len(decisions),
        "total_failures": len(failures),
        "parse_success_rate": (
            sum(1 for d in decisions if d["parse_ok"]) / len(decisions)
            if decisions else 0.0
        ),
        "avg_inference_ms": round(avg_inference, 1),
        "failure_types": _count_by_key(failures, "failure_type"),
    }


def _count_by_key(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts
