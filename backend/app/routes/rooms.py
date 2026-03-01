from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.models.room import Room, RoomPlayer, _generate_code
from app.services import orchestrator


def _broadcast_room(code: str) -> None:
    """Broadcast room-updated to all sockets in the room (best-effort)."""
    try:
        from app import socketio
        room = _rooms.get(code.upper())
        if room:
            socketio.emit("room-updated", room.to_dict(), room=code)
    except Exception:
        pass  # socket broadcast is best-effort

rooms_bp = Blueprint("rooms", __name__)

_rooms: dict[str, Room] = {}


def get_room_store() -> dict[str, Room]:
    return _rooms


# ── REST endpoints ──────────────────────────────────────────────────────────

@rooms_bp.route("/rooms", methods=["POST"])
def create_room():
    """Create a new room and return the room code."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agentId")
    user_id = data.get("userId", "")
    user_name = data.get("userName", "Host")
    user_image = data.get("userImage")

    if not agent_id:
        return jsonify({"error": "agentId is required."}), 400

    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    code = data.get("code") or _generate_code(set(_rooms.keys()))
    room = Room(created_by=user_id, code=code)

    host = RoomPlayer(
        user_id=user_id,
        user_name=user_name,
        agent_id=agent_id,
        agent_name=agent.name,
        user_image=user_image,
        is_host=True,
    )
    room.add_player(host)
    _rooms[code] = room

    return jsonify({"code": code, "room": room.to_dict()}), 201


@rooms_bp.route("/rooms/restore", methods=["POST"])
def restore_room():
    """Recreate a room with a specific code (e.g. after backend restart). Used when join returns 404 but room exists in DB."""
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    user_id = data.get("userId", "")
    user_name = data.get("userName", "Host")
    user_image = data.get("userImage")
    agent_id = data.get("agentId")

    if not code or len(code) < 4:
        return jsonify({"error": "Valid room code is required."}), 400
    if not agent_id:
        return jsonify({"error": "agentId is required."}), 400

    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found. Sync the host's agent first."}), 404

    if code in _rooms:
        return jsonify({"code": code, "room": _rooms[code].to_dict()}), 200

    room = Room(created_by=user_id, code=code)
    host = RoomPlayer(
        user_id=user_id,
        user_name=user_name,
        agent_id=agent_id,
        agent_name=agent.name,
        user_image=user_image,
        is_host=True,
    )
    room.add_player(host)
    _rooms[code] = room

    return jsonify({"code": code, "room": room.to_dict()}), 201


@rooms_bp.route("/rooms/<code>", methods=["GET"])
def get_room(code: str):
    room = _rooms.get(code.upper())
    if not room:
        return jsonify({"error": "Room not found."}), 404
    return jsonify(room.to_dict())


@rooms_bp.route("/rooms/<code>/join", methods=["POST"])
def join_room(code: str):
    room = _rooms.get(code.upper())
    if not room:
        return jsonify({"error": "Room not found."}), 404

    data = request.get_json(silent=True) or {}
    agent_id = data.get("agentId")
    user_id = data.get("userId", "")
    user_name = data.get("userName", "Player")
    user_image = data.get("userImage")

    if not agent_id:
        return jsonify({"error": "agentId is required."}), 400

    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    player = RoomPlayer(
        user_id=user_id,
        user_name=user_name,
        agent_id=agent_id,
        agent_name=agent.name,
        user_image=user_image,
    )
    err = room.add_player(player)
    if err:
        return jsonify({"error": err}), 400

    _broadcast_room(code)
    return jsonify({"room": room.to_dict()})


@rooms_bp.route("/rooms/<code>/leave", methods=["POST"])
def leave_room(code: str):
    room = _rooms.get(code.upper())
    if not room:
        return jsonify({"error": "Room not found."}), 404

    data = request.get_json(silent=True) or {}
    user_id = data.get("userId", "")
    err = room.remove_player(user_id)
    if err:
        return jsonify({"error": err}), 400

    if not room.players:
        del _rooms[code.upper()]
        return jsonify({"message": "Room deleted (empty)."})

    _broadcast_room(code)
    return jsonify({"room": room.to_dict()})


@rooms_bp.route("/rooms/<code>/ready", methods=["POST"])
def toggle_ready(code: str):
    room = _rooms.get(code.upper())
    if not room:
        return jsonify({"error": "Room not found."}), 404

    data = request.get_json(silent=True) or {}
    user_id = data.get("userId", "")
    ready = data.get("ready", True)

    err = room.set_ready(user_id, ready)
    if err:
        return jsonify({"error": err}), 400

    return jsonify({"room": room.to_dict(), "allReady": room.all_ready})
