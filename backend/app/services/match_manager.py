from __future__ import annotations

"""
Match manager: creates matches, tracks lifecycle, records results,
and triggers Elo updates. Acts as the bridge between the game engine
and the orchestrator.

Flow:
  1. POST /api/matches          → create_match()
  2. Game engine calls start()  → match enters RUNNING
  3. After each hand, engine calls record_hand()
  4. Engine calls finish()      → match enters COMPLETED, Elo updated
  5. GET /api/matches/<id>      → full results

The game engine drives the loop; the orchestrator just tracks state.
"""

from app.models.match import Match
from app.services import orchestrator, rating

_matches: dict[str, Match] = {}


# ── Lifecycle ───────────────────────────────────────────────────────────────

def create_match(
    agent_ids: list[str],
    num_hands: int = 100,
    game_type: str = "no_limit_holdem",
    starting_stack: int = 1000,
    small_blind: int = 5,
    big_blind: int = 10,
) -> Match | str:
    """
    Create a new match. Validates that all agents exist.
    Returns the Match or an error string.
    """
    for aid in agent_ids:
        if not orchestrator.get_agent(aid):
            return f"Agent '{aid}' not found."

    if len(agent_ids) < 2:
        return "A match requires at least 2 agents."

    if len(set(agent_ids)) != len(agent_ids):
        return "Duplicate agent IDs."

    match = Match(
        agent_ids=agent_ids,
        num_hands=num_hands,
        game_type=game_type,
        starting_stack=starting_stack,
        small_blind=small_blind,
        big_blind=big_blind,
    )
    _matches[match.id] = match
    return match


def start_match(match_id: str) -> Match | str:
    """Transition match to RUNNING."""
    match = _matches.get(match_id)
    if not match:
        return "Match not found."
    if match.status.value != "pending":
        return f"Cannot start match in '{match.status.value}' state."
    match.start()
    return match


def record_hand(match_id: str, hand_result: dict) -> Match | str:
    """Record a completed hand from the game engine."""
    match = _matches.get(match_id)
    if not match:
        return "Match not found."
    if match.status.value != "running":
        return f"Match is '{match.status.value}', not running."
    match.record_hand(hand_result)
    return match


def finish_match(match_id: str) -> Match | str:
    """
    Complete the match, finalize results, update Elo ratings.
    """
    match = _matches.get(match_id)
    if not match:
        return "Match not found."
    if match.status.value != "running":
        return f"Match is '{match.status.value}', not running."

    match.finish()

    _update_ratings(match)

    return match


def cancel_match(match_id: str) -> Match | str:
    match = _matches.get(match_id)
    if not match:
        return "Match not found."
    if match.status.value in ("completed", "cancelled"):
        return f"Match already '{match.status.value}'."
    match.cancel()
    return match


def fail_match(match_id: str, error: str) -> Match | str:
    match = _matches.get(match_id)
    if not match:
        return "Match not found."
    match.fail(error)
    return match


# ── Queries ─────────────────────────────────────────────────────────────────

def get_match(match_id: str) -> Match | None:
    return _matches.get(match_id)


def list_matches(
    status: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
) -> list[Match]:
    matches = list(_matches.values())
    if status:
        matches = [m for m in matches if m.status.value == status]
    if agent_id:
        matches = [m for m in matches if agent_id in m.agent_ids]
    matches.sort(key=lambda m: m.created_at, reverse=True)
    return matches[:limit]


def get_agent_match_history(agent_id: str) -> list[dict]:
    """Get summarized match history for an agent."""
    history = []
    for m in _matches.values():
        if agent_id not in m.agent_ids:
            continue
        agent_result = m.results.get(agent_id)
        history.append({
            "match_id": m.id,
            "status": m.status.value,
            "opponent_ids": [a for a in m.agent_ids if a != agent_id],
            "net_chips": agent_result.net_chips if agent_result else 0,
            "hands_won": agent_result.hands_won if agent_result else 0,
            "hands_played": agent_result.hands_played if agent_result else 0,
            "is_winner": m.winner_id == agent_id,
            "created_at": m.created_at,
        })
    history.sort(key=lambda h: h["created_at"], reverse=True)
    return history


# ── Rating Integration ──────────────────────────────────────────────────────

def _update_ratings(match: Match):
    """Compute and apply Elo updates from a completed match."""
    if len(match.agent_ids) == 2:
        a, b = match.agent_ids
        result_a = match.results.get(a)
        result_b = match.results.get(b)
        if not result_a or not result_b:
            return

        if result_a.net_chips > result_b.net_chips:
            rating.record_match_result(winner_id=a, loser_id=b, match_id=match.id)
        elif result_b.net_chips > result_a.net_chips:
            rating.record_match_result(winner_id=b, loser_id=a, match_id=match.id)
        else:
            rating.record_match_result(winner_id=a, loser_id=b, match_id=match.id, draw=True)
    else:
        ranked = sorted(
            match.agent_ids,
            key=lambda aid: match.results[aid].net_chips if aid in match.results else 0,
            reverse=True,
        )
        rating.record_match_result(winner_id=None, loser_id=None, match_id=match.id, agent_ids=ranked)
