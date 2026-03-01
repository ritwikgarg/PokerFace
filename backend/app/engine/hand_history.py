from __future__ import annotations

"""
Immutable hand history records for auditing, replay, and debugging.
Given a hand history + seed, the engine can replay the hand deterministically.
"""

import copy
from datetime import datetime, timezone


class HandHistory:
    """Captures a complete, immutable record of a single poker hand."""

    def __init__(self, hand_summary: dict, table_id: str):
        self.table_id = table_id
        self.hand_id = hand_summary.get("hand_id", "unknown")
        self.hand_number = hand_summary.get("hand_number", 0)
        self.seed = hand_summary.get("seed")
        self.winners = hand_summary.get("winners", [])
        self.pot = hand_summary.get("pot", 0)
        self.community_cards = hand_summary.get("community_cards", [])
        self.action_log = copy.deepcopy(hand_summary.get("action_log", []))
        self.player_results = hand_summary.get("player_results", {})
        self.recorded_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "hand_id": self.hand_id,
            "hand_number": self.hand_number,
            "seed": self.seed,
            "winners": self.winners,
            "pot": self.pot,
            "community_cards": self.community_cards,
            "action_log": self.action_log,
            "player_results": self.player_results,
            "recorded_at": self.recorded_at,
        }

    @property
    def is_replayable(self) -> bool:
        return self.seed is not None and len(self.action_log) > 0


# ── In-memory store ─────────────────────────────────────────────────────────
_histories: list[HandHistory] = []


def record(hand_summary: dict, table_id: str) -> HandHistory:
    h = HandHistory(hand_summary, table_id)
    _histories.append(h)
    return h


def get_by_hand_id(hand_id: str) -> HandHistory | None:
    for h in _histories:
        if h.hand_id == hand_id:
            return h
    return None


def get_by_table(table_id: str, limit: int = 100) -> list[HandHistory]:
    return [h for h in reversed(_histories) if h.table_id == table_id][:limit]


def get_all(limit: int = 200) -> list[HandHistory]:
    return list(reversed(_histories))[:limit]
