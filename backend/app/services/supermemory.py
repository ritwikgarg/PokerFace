from __future__ import annotations

"""
Supermemory integration — persistent cross-game memory for agents.

Stores structured events (hand summaries, opponent notes, self-learnings)
in Supermemory's vector store. Retrieves relevant context via semantic
search before each decision.

The in-memory AgentMemory (memory.py) handles within-game context.
This module handles everything that persists *across* games.

Requires SUPERMEMORY_API_KEY env var. Degrades gracefully if unavailable.
"""

import json
import os
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Event types
HAND_SUMMARY = "HAND_SUMMARY"
OPPONENT_NOTE = "OPPONENT_NOTE"
SELF_LEARNING = "SELF_LEARNING"
TOURNAMENT_STATE = "TOURNAMENT_STATE"


def _base_url() -> str:
    return os.getenv("SUPERMEMORY_API_URL", "https://api.supermemory.ai")


def _api_key() -> str:
    return os.getenv("SUPERMEMORY_API_KEY", "")


def _openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")


def _is_configured() -> bool:
    return bool(_api_key())


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def _agent_space(agent_id: str) -> str:
    return f"agent_{agent_id}"


# ── Write ────────────────────────────────────────────────────────────────────


def write_event(
    game_id: str,
    agent_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str | None:
    """Store a memory event in Supermemory. Returns event content or None on failure."""
    if not _is_configured():
        logger.debug("Supermemory not configured, skipping write")
        return None

    content = _event_to_text(event_type, payload)
    metadata = {
        "game_id": game_id,
        "agent_id": agent_id,
        "event_type": event_type,
        "ts": time.time(),
        **{k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool))},
    }

    try:
        resp = httpx.post(
            f"{_base_url()}/v3/documents",
            headers=_headers(),
            json={
                "content": content,
                "containerTag": _agent_space(agent_id),
                "metadata": metadata,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info(f"Wrote {event_type} event for agent {agent_id[:8]}")
        return content
    except Exception as e:
        logger.warning(f"Supermemory write failed: {e}")
        return None


def write_hand_summary(
    game_id: str,
    agent_id: str,
    position: str,
    hole_cards: list[str],
    board: list[str],
    actions_taken: list[str],
    result: str,
    pot_size: int,
    key_decision: str = "",
    lessons: list[str] | None = None,
) -> str | None:
    """Convenience wrapper for writing a hand summary event."""
    return write_event(game_id, agent_id, HAND_SUMMARY, {
        "position": position,
        "hole_cards": hole_cards,
        "board": board,
        "actions_taken": actions_taken,
        "result": result,
        "pot_size": pot_size,
        "key_decision": key_decision,
        "lessons": lessons or [],
    })


def write_opponent_note(
    game_id: str,
    agent_id: str,
    opponent_id: str,
    tag: str,
    notes: str = "",
    street: str = "",
    confidence: float = 0.6,
) -> str | None:
    """Convenience wrapper for writing an opponent note."""
    return write_event(game_id, agent_id, OPPONENT_NOTE, {
        "opponent_id": opponent_id,
        "tag": tag,
        "notes": notes,
        "street": street,
        "confidence": confidence,
    })


def write_self_learning(
    game_id: str,
    agent_id: str,
    leak: str,
    fix: str,
    severity: float = 0.5,
) -> str | None:
    """Convenience wrapper for writing a self-learning event."""
    return write_event(game_id, agent_id, SELF_LEARNING, {
        "leak": leak,
        "fix": fix,
        "severity": severity,
    })


# ── Read / Retrieve ─────────────────────────────────────────────────────────


def get_context(
    agent_id: str,
    query: str,
    top_k: int = 5,
    game_id: str | None = None,
) -> list[dict]:
    """Semantic search over an agent's memory. Returns list of snippets."""
    if not _is_configured():
        return []

    body: dict[str, Any] = {
        "q": query,
        "containerTag": _agent_space(agent_id),
        "limit": top_k,
        "searchMode": "hybrid",
    }

    if game_id:
        body["filters"] = {
            "AND": [{"filterType": "metadata", "key": "game_id", "value": game_id}]
        }

    try:
        resp = httpx.post(
            f"{_base_url()}/v4/search",
            headers=_headers(),
            json=body,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        snippets = []
        for item in data.get("results", []):
            # hybrid mode returns "chunk" (str), memories mode returns "memory" (str)
            content = ""
            if isinstance(item.get("chunk"), str):
                content = item["chunk"]
            elif isinstance(item.get("memory"), str):
                content = item["memory"]
            elif isinstance(item.get("chunk"), dict):
                content = item["chunk"].get("content", "")
            elif isinstance(item.get("memory"), dict):
                content = item["memory"].get("content", "")

            meta = item.get("metadata") or {}
            snippets.append({
                "content": content,
                "score": item.get("similarity", 0.0),
                "event_type": meta.get("event_type", ""),
                "game_id": meta.get("game_id", ""),
                "ts": meta.get("ts", 0.0),
            })
        return snippets

    except Exception as e:
        logger.warning(f"Supermemory search failed: {e}")
        return []


def get_decision_context(
    agent_id: str,
    opponent_ids: list[str],
    street: str,
    board: list[str],
    history_level: int = 0,
) -> str:
    """Build a memory context block for injection into the agent's prompt.

    ``history_level`` controls how much data is retrieved from Supermemory:
      0 — disabled, return immediately
      1 — minimal: 1 broad query, 2 results
      2 — moderate: opponent + self-learning queries, 4 results
      3 — full: opponents + self-learnings + board texture, 10 results

    The raw snippets are then summarized by GPT-4o mini before injection.
    """
    if history_level <= 0 or not _is_configured():
        return ""

    all_snippets: list[dict] = []
    seen: set[str] = set()

    def _collect(results: list[dict]) -> None:
        for s in results:
            key = s["content"][:80]
            if key not in seen:
                seen.add(key)
                all_snippets.append(s)

    if history_level == 1:
        _collect(get_context(
            agent_id,
            f"Key highlights and lessons from my past poker games on {street}.",
            top_k=2,
        ))

    elif history_level == 2:
        for opp_id in opponent_ids[:2]:
            _collect(get_context(
                agent_id,
                f"How does {opp_id} play on {street}? Tendencies and patterns.",
                top_k=2,
            ))
        _collect(get_context(
            agent_id,
            f"My leaks and mistakes on {street}. What should I avoid?",
            top_k=2,
        ))

    else:
        for opp_id in opponent_ids[:3]:
            _collect(get_context(
                agent_id,
                f"How does {opp_id} play on {street}? Tendencies and patterns.",
                top_k=3,
            ))
        _collect(get_context(
            agent_id,
            f"My leaks and mistakes on {street}. What should I avoid?",
            top_k=3,
        ))
        if board:
            board_str = " ".join(board)
            _collect(get_context(
                agent_id,
                f"Past hands with similar board to {board_str}. Lessons learned.",
                top_k=3,
            ))

    all_snippets.sort(key=lambda s: s.get("score", 0), reverse=True)
    max_results = {1: 2, 2: 4, 3: 10}.get(history_level, 6)
    top = all_snippets[:max_results]

    if not top:
        return ""

    raw_text = "\n".join(
        f"[{s.get('event_type', 'NOTE')}] {s['content']}" for s in top
    )

    summarized = _summarize_with_gpt4o_mini(raw_text, street, history_level)
    return summarized


# ── GPT-4o mini summarization ───────────────────────────────────────────────


_SUMMARY_PROMPTS = {
    1: (
        "You are a poker assistant. Summarize the following past game notes into "
        "1-2 short bullet points. Keep only the most actionable insight. "
        "Be extremely concise (under 80 words)."
    ),
    2: (
        "You are a poker assistant. Summarize the following past game notes into "
        "3-4 bullet points covering opponent tendencies and your own leaks. "
        "Be concise but include key patterns (under 150 words)."
    ),
    3: (
        "You are a poker assistant. Summarize the following past game notes into "
        "a comprehensive briefing. Cover opponent profiles, your known leaks, "
        "and any relevant board/situation patterns. Be thorough but organized "
        "(under 300 words)."
    ),
}


def _summarize_with_gpt4o_mini(raw_text: str, street: str, level: int) -> str:
    """Call OpenAI GPT-4o mini to condense raw Supermemory snippets.

    Falls back to the raw text (truncated) if the API key is missing or
    the call fails, so the agent still gets *some* context.
    """
    openai_key = _openai_key()
    if not openai_key:
        logger.debug("OPENAI_API_KEY not set, returning raw snippets")
        return f"=== Previous Games Context ===\n{raw_text[:500]}"

    system = _SUMMARY_PROMPTS.get(level, _SUMMARY_PROMPTS[2])

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": (
                            f"Current street: {street}\n\n"
                            f"Raw notes from past games:\n{raw_text}"
                        ),
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        summary = resp.json()["choices"][0]["message"]["content"].strip()
        return f"=== Previous Games Context ===\n{summary}"
    except Exception as e:
        logger.warning(f"GPT-4o mini summarization failed: {e}")
        return f"=== Previous Games Context ===\n{raw_text[:500]}"


# ── Post-hand summarization ─────────────────────────────────────────────────


def summarize_and_store(
    game_id: str,
    agent_id: str,
    hand_id: str,
    hole_cards: list[str],
    board: list[str],
    position: str,
    actions: list[str],
    result: str,
    pot_size: int,
    opponents: list[str] | None = None,
) -> None:
    """After a hand completes, store a compact summary in Supermemory.

    This is called from the game turn protocol after each hand ends.
    Keeps it simple — no separate LLM call for summarization, just
    structured storage of the key facts.
    """
    key_decision = ""
    for action in reversed(actions):
        if "raise" in action.lower() or "all" in action.lower():
            key_decision = action
            break
    if not key_decision and actions:
        key_decision = actions[-1]

    lessons = []
    if "lost" in result.lower():
        lessons.append(f"Lost hand — review {position} play with {' '.join(hole_cards)}")
    if "won" in result.lower() and pot_size > 200:
        lessons.append(f"Big pot win — {position} strategy worked")

    write_hand_summary(
        game_id=game_id,
        agent_id=agent_id,
        position=position,
        hole_cards=hole_cards,
        board=board,
        actions_taken=actions,
        result=result,
        pot_size=pot_size,
        key_decision=key_decision,
        lessons=lessons,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event_to_text(event_type: str, payload: dict) -> str:
    """Convert structured event into searchable text for embedding."""
    if event_type == HAND_SUMMARY:
        cards = payload.get("hole_cards", [])
        board = payload.get("board", [])
        return (
            f"Hand in position {payload.get('position', '?')}: "
            f"cards {' '.join(cards)}, board {' '.join(board)}, "
            f"result {payload.get('result', '?')}. "
            f"Key: {payload.get('key_decision', '')}. "
            f"Lessons: {', '.join(payload.get('lessons', []))}."
        )
    elif event_type == OPPONENT_NOTE:
        return (
            f"Opponent {payload.get('opponent_id', '?')}: "
            f"{payload.get('tag', '')}. {payload.get('notes', '')}."
        )
    elif event_type == SELF_LEARNING:
        return (
            f"Leak: {payload.get('leak', '')}. "
            f"Fix: {payload.get('fix', '')}."
        )
    elif event_type == TOURNAMENT_STATE:
        return (
            f"Bankroll: {payload.get('bankroll', 0)}, "
            f"streak: {payload.get('streak', '')}."
        )
    return json.dumps(payload)[:300]


def status() -> dict:
    """Health check for Supermemory integration."""
    return {
        "configured": _is_configured(),
        "base_url": _base_url(),
        "has_api_key": bool(_api_key()),
    }
