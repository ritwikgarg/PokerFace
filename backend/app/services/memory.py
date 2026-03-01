from __future__ import annotations

"""
Per-agent per-game memory system.

Two layers:
  1. Rolling summary — factual log of what happened (cards, actions, outcomes).
     Compact, append-only, auto-summarized when it exceeds a size limit.
  2. Strategy layer — risk posture, opponent reads, commitments, human nudges.
     Updated by the agent's own reasoning output and external nudges.

Memory is game-scoped: it resets between games unless configured otherwise.
Growth is bounded with hard token limits and automatic truncation.
"""

import uuid
from datetime import datetime, timezone

MAX_SUMMARY_CHARS = 4000
MAX_STRATEGY_CHARS = 2000
MAX_ENTRIES_PER_LAYER = 50


class AgentMemory:
    def __init__(self, agent_id: str, game_id: str):
        self.id = str(uuid.uuid4())
        self.agent_id = agent_id
        self.game_id = game_id
        self.summary_entries: list[dict] = []
        self.strategy_entries: list[dict] = []
        self.nudges: list[dict] = []
        self.reasoning_traces: list[dict] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    # ── Rolling Summary ─────────────────────────────────────────────────────

    def add_summary(self, content: str, hand_number: int | None = None):
        self.summary_entries.append({
            "content": content,
            "hand_number": hand_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._enforce_summary_limit()

    def get_summary_text(self) -> str:
        return "\n".join(e["content"] for e in self.summary_entries)

    def _enforce_summary_limit(self):
        while len(self.summary_entries) > MAX_ENTRIES_PER_LAYER:
            self.summary_entries.pop(0)
        total = sum(len(e["content"]) for e in self.summary_entries)
        while total > MAX_SUMMARY_CHARS and len(self.summary_entries) > 2:
            removed = self.summary_entries.pop(0)
            total -= len(removed["content"])

    # ── Strategy Layer ──────────────────────────────────────────────────────

    def add_strategy_note(self, content: str, source: str = "agent"):
        """source: 'agent' (from reasoning), 'nudge' (from human), 'system'."""
        self.strategy_entries.append({
            "content": content,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._enforce_strategy_limit()

    def get_strategy_text(self) -> str:
        return "\n".join(f"[{e['source']}] {e['content']}" for e in self.strategy_entries)

    def _enforce_strategy_limit(self):
        while len(self.strategy_entries) > MAX_ENTRIES_PER_LAYER:
            self.strategy_entries.pop(0)
        total = sum(len(e["content"]) for e in self.strategy_entries)
        while total > MAX_STRATEGY_CHARS and len(self.strategy_entries) > 2:
            removed = self.strategy_entries.pop(0)
            total -= len(removed["content"])

    # ── Human Nudges ────────────────────────────────────────────────────────

    def add_nudge(self, message: str, from_user: str):
        nudge = {
            "message": message,
            "from_user": from_user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.nudges.append(nudge)
        self.add_strategy_note(f"Human nudge from {from_user}: {message}", source="nudge")
        return nudge

    # ── Reasoning Traces ────────────────────────────────────────────────────

    def add_reasoning_trace(self, hand_id: str, action: dict, reasoning: str,
                            memory_update: str | None = None):
        trace = {
            "hand_id": hand_id,
            "action": action,
            "reasoning": reasoning,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.reasoning_traces.append(trace)
        if memory_update:
            self.add_strategy_note(memory_update, source="agent")

    # ── Build context for next turn ─────────────────────────────────────────

    def build_memory_context(self, long_term_context: str = "") -> str:
        """Assemble the full memory context to inject into the agent's prompt.

        Args:
            long_term_context: Pre-fetched Supermemory context (cross-game memory).
                               Pass empty string if Supermemory is not configured.
        """
        sections = []

        summary = self.get_summary_text()
        if summary:
            sections.append(f"=== Game History ===\n{summary}")

        strategy = self.get_strategy_text()
        if strategy:
            sections.append(f"=== Strategy Notes ===\n{strategy}")

        if long_term_context:
            sections.append(long_term_context)

        return "\n\n".join(sections) if sections else ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "game_id": self.game_id,
            "summary_entries": len(self.summary_entries),
            "strategy_entries": len(self.strategy_entries),
            "nudges": len(self.nudges),
            "reasoning_traces": len(self.reasoning_traces),
            "created_at": self.created_at,
        }


# ── In-memory store keyed by (agent_id, game_id) ───────────────────────────
_memories: dict[tuple[str, str], AgentMemory] = {}


def get_or_create(agent_id: str, game_id: str) -> AgentMemory:
    key = (agent_id, game_id)
    if key not in _memories:
        _memories[key] = AgentMemory(agent_id, game_id)
    return _memories[key]


def get_memory(agent_id: str, game_id: str) -> AgentMemory | None:
    return _memories.get((agent_id, game_id))


def clear_game_memories(game_id: str):
    to_remove = [k for k in _memories if k[1] == game_id]
    for k in to_remove:
        del _memories[k]


def list_memories(agent_id: str | None = None) -> list[AgentMemory]:
    if agent_id:
        return [m for m in _memories.values() if m.agent_id == agent_id]
    return list(_memories.values())
