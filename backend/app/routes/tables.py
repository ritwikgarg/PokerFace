from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.engine.table import Table
from app.engine.state_snapshot import build_public_state, build_player_view
from app.engine import hand_history
from app.services import file_logger

tables_bp = Blueprint("tables", __name__)

# In-memory table store
_tables: dict[str, Table] = {}


def _get_table(table_id: str):
    return _tables.get(table_id)


@tables_bp.route("/tables", methods=["POST"])
def create_table():
    data = request.get_json(silent=True) or {}
    table = Table(
        max_seats=data.get("max_seats", 6),
        small_blind=data.get("small_blind", 5),
        big_blind=data.get("big_blind", 10),
        starting_stack=data.get("starting_stack", 1000),
        match_id=data.get("match_id"),
    )
    if data.get("seed_base"):
        table.hand_seed_base = data["seed_base"]
    _tables[table.id] = table
    return jsonify(table.to_dict()), 201


@tables_bp.route("/tables", methods=["GET"])
def list_tables():
    return jsonify([t.to_dict() for t in _tables.values()])


@tables_bp.route("/tables/<table_id>", methods=["GET"])
def get_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    return jsonify(table.to_dict())


@tables_bp.route("/tables/<table_id>/join", methods=["POST"])
def join_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404

    data = request.get_json(silent=True) or {}
    player_id = data.get("player_id")
    if not player_id:
        return jsonify({"error": "'player_id' is required."}), 422

    result = table.join(
        player_id=player_id,
        player_type=data.get("player_type", "agent"),
        seat_index=data.get("seat_index"),
        buy_in=data.get("buy_in"),
    )
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result.to_dict())


@tables_bp.route("/tables/<table_id>/leave", methods=["POST"])
def leave_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404

    data = request.get_json(silent=True) or {}
    error = table.leave(data.get("player_id", ""))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Left table."})


@tables_bp.route("/tables/<table_id>/start-hand", methods=["POST"])
def start_hand(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404

    data = request.get_json(silent=True) or {}
    result = table.start_hand(seed=data.get("seed"))
    if isinstance(result, str):
        return jsonify({"error": result}), 400

    poker_hand, events = result
    return jsonify({
        "hand_id": poker_hand.hand_id,
        "phase": poker_hand.phase.value,
        "events": events,
        "current_player_id": poker_hand.current_player.player_id if poker_hand.current_player else None,
        "table": build_public_state(table),
    })


@tables_bp.route("/tables/<table_id>/action", methods=["POST"])
def submit_action(table_id: str):
    """Submit a player action. The engine validates and applies it."""
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    if not table.current_hand:
        return jsonify({"error": "No active hand."}), 400

    data = request.get_json(silent=True) or {}
    player_id = data.get("player_id")
    action = data.get("action", {})

    if not player_id:
        return jsonify({"error": "'player_id' is required."}), 422

    try:
        events = table.current_hand.apply_action(player_id, action)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    response = {"events": events}

    if table.current_hand.is_hand_over:
        summary = table.finish_hand()
        if not isinstance(summary, str):
            hand_history.record(summary, table_id)
            file_logger.log_hand_result(table_id, summary)
            response["hand_complete"] = True
            response["summary"] = summary
    else:
        cp = table.current_hand.current_player
        response["hand_complete"] = False
        response["next_player_id"] = cp.player_id if cp else None

    response["table"] = build_public_state(table)
    return jsonify(response)


@tables_bp.route("/tables/<table_id>/finish-hand", methods=["POST"])
def finish_current_hand(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404

    result = table.finish_hand()
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    hand_history.record(result, table_id)
    return jsonify(result)


@tables_bp.route("/tables/<table_id>/player-view/<player_id>", methods=["GET"])
def get_player_view(table_id: str, player_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    return jsonify(build_player_view(table, player_id))


@tables_bp.route("/tables/<table_id>/pause", methods=["POST"])
def pause_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    table.pause()
    return jsonify({"status": table.status.value})


@tables_bp.route("/tables/<table_id>/resume", methods=["POST"])
def resume_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    table.resume()
    return jsonify({"status": table.status.value})


@tables_bp.route("/tables/<table_id>/finish", methods=["POST"])
def finish_table(table_id: str):
    table = _get_table(table_id)
    if not table:
        return jsonify({"error": "Table not found."}), 404
    from app.services.modal_workers import stop_table_workers
    stop_table_workers(table_id)
    table.finish_table()
    return jsonify({"status": table.status.value})


@tables_bp.route("/tables/<table_id>/history", methods=["GET"])
def get_hand_history(table_id: str):
    limit = int(request.args.get("limit", 100))
    histories = hand_history.get_by_table(table_id, limit=limit)
    return jsonify([h.to_dict() for h in histories])


def get_table_store() -> dict[str, Table]:
    """Expose table store for socket events and orchestrator integration."""
    return _tables
