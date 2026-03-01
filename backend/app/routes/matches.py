from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services import match_manager

matches_bp = Blueprint("matches", __name__)


@matches_bp.route("/matches", methods=["POST"])
def create_match():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    agent_ids = data.get("agent_ids")
    if not agent_ids or not isinstance(agent_ids, list):
        return jsonify({"error": "'agent_ids' must be a list of agent UUIDs."}), 422

    result = match_manager.create_match(
        agent_ids=agent_ids,
        num_hands=data.get("num_hands", 100),
        game_type=data.get("game_type", "no_limit_holdem"),
        starting_stack=data.get("starting_stack", 1000),
        small_blind=data.get("small_blind", 5),
        big_blind=data.get("big_blind", 10),
    )
    if isinstance(result, str):
        return jsonify({"error": result}), 422
    return jsonify(result.to_dict()), 201


@matches_bp.route("/matches", methods=["GET"])
def list_matches():
    status = request.args.get("status")
    agent_id = request.args.get("agent_id")
    limit = int(request.args.get("limit", 50))
    matches = match_manager.list_matches(status=status, agent_id=agent_id, limit=limit)
    return jsonify([m.to_dict() for m in matches])


@matches_bp.route("/matches/<match_id>", methods=["GET"])
def get_match(match_id: str):
    match = match_manager.get_match(match_id)
    if not match:
        return jsonify({"error": "Match not found."}), 404
    include_log = request.args.get("include_hand_log", "false").lower() == "true"
    return jsonify(match.to_dict(include_hand_log=include_log))


@matches_bp.route("/matches/<match_id>/start", methods=["POST"])
def start_match(match_id: str):
    """Game engine calls this to begin the match."""
    result = match_manager.start_match(match_id)
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result.to_dict())


@matches_bp.route("/matches/<match_id>/hands", methods=["POST"])
def record_hand(match_id: str):
    """
    Game engine calls this after each hand completes.

    Expected body:
    {
      "hand_id": "...",
      "hand_number": 1,
      "winner_ids": ["agent-uuid"],
      "pot": 200,
      "chip_deltas": {"agent-uuid-1": 100, "agent-uuid-2": -100},
      "actions_taken": 12,
      "showdown": true
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    result = match_manager.record_hand(match_id, data)
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify({
        "current_hand": result.current_hand,
        "num_hands": result.num_hands,
    })


@matches_bp.route("/matches/<match_id>/finish", methods=["POST"])
def finish_match(match_id: str):
    """Game engine calls this when all hands are done. Triggers Elo update."""
    result = match_manager.finish_match(match_id)
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result.to_dict())


@matches_bp.route("/matches/<match_id>/cancel", methods=["POST"])
def cancel_match(match_id: str):
    result = match_manager.cancel_match(match_id)
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result.to_dict())
