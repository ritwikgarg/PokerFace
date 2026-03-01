from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services import rating, match_manager, orchestrator

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """Return leaderboard in the shape the frontend LeaderboardEntry[] expects.

    Frontend interface:
        { rank, user: { id, name, image, githubUsername },
          agentName, gamesPlayed, winRate, totalEarnings, biggestPot }
    """
    limit = int(request.args.get("limit", 50))
    board = rating.leaderboard(limit=limit)

    entries = []
    for i, entry in enumerate(board):
        agent = orchestrator.get_agent(entry["agent_id"])
        agent_name = agent.name if agent else "(deleted)"
        user_id = agent.user_id if agent else ""

        matches_played = entry.get("matches_played", 0)
        wins = entry.get("wins", 0)
        win_rate = (wins / matches_played * 100) if matches_played > 0 else 0.0

        entries.append({
            "rank": i + 1,
            "user": {
                "id": user_id,
                "name": user_id or "Unknown",
                "image": "",
                "githubUsername": "",
            },
            "agentName": agent_name,
            "gamesPlayed": matches_played,
            "winRate": round(win_rate, 1),
            "totalEarnings": entry.get("rating", 1200) - 1200,
            "biggestPot": 0,
        })

    return jsonify(entries)


@leaderboard_bp.route("/leaderboard/<agent_id>", methods=["GET"])
def get_agent_stats(agent_id: str):
    """Full stats for a single agent: rating + match history."""
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    agent_rating = rating.get_rating(agent_id)
    include_history = request.args.get("include_history", "false").lower() == "true"

    return jsonify({
        "agent": agent.to_dict(),
        "rating": agent_rating.to_dict(include_history=include_history) if agent_rating else None,
        "match_history": match_manager.get_agent_match_history(agent_id),
    })
