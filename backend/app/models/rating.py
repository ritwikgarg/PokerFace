from __future__ import annotations

from datetime import datetime, timezone


class AgentRating:
    """
    Tracks an agent's Elo rating across matches.
    Uses standard Elo with configurable K-factor.
    """

    DEFAULT_RATING = 1200
    DEFAULT_K = 32

    def __init__(self, agent_id: str, rating: float | None = None):
        self.agent_id = agent_id
        self.rating = rating if rating is not None else self.DEFAULT_RATING
        self.matches_played = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0
        self.history: list[dict] = []
        self.peak_rating = self.rating
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    @property
    def win_rate(self) -> float | None:
        if self.matches_played == 0:
            return None
        return self.wins / self.matches_played

    def expected_score(self, opponent_rating: float) -> float:
        return 1.0 / (1.0 + 10 ** ((opponent_rating - self.rating) / 400))

    def update(self, actual_score: float, opponent_rating: float, match_id: str):
        """
        Update rating after a match.
        actual_score: 1.0 for win, 0.5 for draw, 0.0 for loss.
        """
        expected = self.expected_score(opponent_rating)
        k = self._dynamic_k()
        delta = k * (actual_score - expected)
        old_rating = self.rating
        self.rating += delta

        self.matches_played += 1
        if actual_score == 1.0:
            self.wins += 1
        elif actual_score == 0.0:
            self.losses += 1
        else:
            self.draws += 1

        if self.rating > self.peak_rating:
            self.peak_rating = self.rating

        self.history.append({
            "match_id": match_id,
            "old_rating": round(old_rating, 1),
            "new_rating": round(self.rating, 1),
            "delta": round(delta, 1),
            "opponent_rating": round(opponent_rating, 1),
            "actual_score": actual_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def _dynamic_k(self) -> float:
        """Higher K for new agents (more volatile), lower for established ones."""
        if self.matches_played < 10:
            return 40
        if self.matches_played < 30:
            return self.DEFAULT_K
        return 24

    def to_dict(self, include_history: bool = False) -> dict:
        d = {
            "agent_id": self.agent_id,
            "rating": round(self.rating, 1),
            "matches_played": self.matches_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": round(self.win_rate, 3) if self.win_rate is not None else None,
            "peak_rating": round(self.peak_rating, 1),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_history:
            d["history"] = self.history
        return d
