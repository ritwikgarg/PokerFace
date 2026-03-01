from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum


class MatchStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class Match:
    """
    A match between two or more agents over N hands.
    The game engine runs the hands; the orchestrator tracks lifecycle and results.
    """

    def __init__(
        self,
        agent_ids: list[str],
        num_hands: int = 100,
        match_id: str | None = None,
        game_type: str = "no_limit_holdem",
        starting_stack: int = 1000,
        small_blind: int = 5,
        big_blind: int = 10,
    ):
        self.id = match_id or str(uuid.uuid4())
        self.agent_ids = agent_ids
        self.num_hands = num_hands
        self.game_type = game_type
        self.starting_stack = starting_stack
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.status = MatchStatus.PENDING
        self.current_hand = 0
        self.results: dict[str, MatchAgentResult] = {
            aid: MatchAgentResult(aid) for aid in agent_ids
        }
        self.hand_log: list[dict] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.error_message: str | None = None

    def start(self):
        self.status = MatchStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def record_hand(self, hand_result: dict):
        """
        Record a completed hand. Expected shape:
        {
            "hand_id": "...",
            "hand_number": 1,
            "winner_ids": ["agent-uuid"],
            "pot": 200,
            "chip_deltas": {"agent-uuid-1": +100, "agent-uuid-2": -100},
            "actions_taken": 12,
            "showdown": true
        }
        """
        self.hand_log.append(hand_result)
        self.current_hand = len(self.hand_log)
        for aid, delta in hand_result.get("chip_deltas", {}).items():
            if aid in self.results:
                self.results[aid].record_hand(delta, aid in hand_result.get("winner_ids", []))

    def finish(self):
        self.status = MatchStatus.COMPLETED
        self.finished_at = datetime.now(timezone.utc).isoformat()
        for r in self.results.values():
            r.finalize()

    def fail(self, error: str):
        self.status = MatchStatus.ERROR
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.error_message = error

    def cancel(self):
        self.status = MatchStatus.CANCELLED
        self.finished_at = datetime.now(timezone.utc).isoformat()

    @property
    def winner_id(self) -> str | None:
        if self.status != MatchStatus.COMPLETED:
            return None
        best = max(self.results.values(), key=lambda r: r.net_chips, default=None)
        return best.agent_id if best else None

    def to_dict(self, include_hand_log: bool = False) -> dict:
        d = {
            "id": self.id,
            "agent_ids": self.agent_ids,
            "game_type": self.game_type,
            "num_hands": self.num_hands,
            "starting_stack": self.starting_stack,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "status": self.status.value,
            "current_hand": self.current_hand,
            "results": {aid: r.to_dict() for aid, r in self.results.items()},
            "winner_id": self.winner_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_message": self.error_message,
        }
        if include_hand_log:
            d["hand_log"] = self.hand_log
        return d


class MatchAgentResult:
    """Per-agent stats within a single match."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.hands_played = 0
        self.hands_won = 0
        self.net_chips = 0
        self.biggest_win = 0
        self.biggest_loss = 0
        self.win_rate: float | None = None

    def record_hand(self, chip_delta: int, won: bool):
        self.hands_played += 1
        self.net_chips += chip_delta
        if won:
            self.hands_won += 1
        if chip_delta > self.biggest_win:
            self.biggest_win = chip_delta
        if chip_delta < self.biggest_loss:
            self.biggest_loss = chip_delta

    def finalize(self):
        if self.hands_played > 0:
            self.win_rate = self.hands_won / self.hands_played

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "hands_played": self.hands_played,
            "hands_won": self.hands_won,
            "net_chips": self.net_chips,
            "biggest_win": self.biggest_win,
            "biggest_loss": self.biggest_loss,
            "win_rate": self.win_rate,
        }
