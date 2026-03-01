from __future__ import annotations

"""
Elo rating service. Maintains in-memory ratings for all agents.
Called by the match manager after a match completes.
"""

from app.models.rating import AgentRating

_ratings: dict[str, AgentRating] = {}


def get_or_create(agent_id: str) -> AgentRating:
    if agent_id not in _ratings:
        _ratings[agent_id] = AgentRating(agent_id)
    return _ratings[agent_id]


def get_rating(agent_id: str) -> AgentRating | None:
    return _ratings.get(agent_id)


def record_match_result(
    winner_id: str | None,
    loser_id: str | None,
    match_id: str,
    draw: bool = False,
    agent_ids: list[str] | None = None,
):
    """
    Update ratings for a completed match.

    For a 2-player match: pass winner_id and loser_id (or draw=True with both).
    For multi-player: pass agent_ids ranked by final chip count (first = best).
    """
    if draw and winner_id and loser_id:
        r_a = get_or_create(winner_id)
        r_b = get_or_create(loser_id)
        opp_a = r_b.rating
        opp_b = r_a.rating
        r_a.update(0.5, opp_a, match_id)
        r_b.update(0.5, opp_b, match_id)
        return

    if winner_id and loser_id:
        r_w = get_or_create(winner_id)
        r_l = get_or_create(loser_id)
        opp_w = r_l.rating
        opp_l = r_w.rating
        r_w.update(1.0, opp_w, match_id)
        r_l.update(0.0, opp_l, match_id)
        return

    if agent_ids and len(agent_ids) > 2:
        _record_multiplayer(agent_ids, match_id)


def _record_multiplayer(ranked_ids: list[str], match_id: str):
    """
    For N-player matches, each player plays a virtual match against
    every other. Pairwise Elo updates with scaled scores.
    """
    n = len(ranked_ids)
    ratings_before = {aid: get_or_create(aid).rating for aid in ranked_ids}

    for i, aid_a in enumerate(ranked_ids):
        for j, aid_b in enumerate(ranked_ids):
            if i >= j:
                continue
            r_a = get_or_create(aid_a)
            r_b = get_or_create(aid_b)
            # Higher rank (lower index) = winner
            r_a.update(1.0, ratings_before[aid_b], match_id)
            r_b.update(0.0, ratings_before[aid_a], match_id)


def leaderboard(limit: int = 50) -> list[dict]:
    """Return agents sorted by rating (descending)."""
    sorted_ratings = sorted(_ratings.values(), key=lambda r: r.rating, reverse=True)
    result = []
    for rank, r in enumerate(sorted_ratings[:limit], 1):
        d = r.to_dict()
        d["rank"] = rank
        result.append(d)
    return result


def reset_all():
    """For testing. Clears all ratings."""
    _ratings.clear()
