from __future__ import annotations

"""
Socket.IO events for real-time game communication.

Frontend event contract (from use-game-socket.ts):

  Client → Server:
    join-room         { roomCode, userId }
    leave-room        { roomCode }
    toggle-ready      { roomCode }
    start-game        { roomCode }
    player-action     { roomCode, seatIndex, action, amount? }

  Server → Client:
    room-updated      Room dict (full lobby snapshot, sent on any lobby mutation)
    game-started      GameState (full snapshot when game begins)
    game-state        GameState (full snapshot on join/reconnect)
    game:turn         { seatIndex, player_id, phase }
    game:player_thinking { seatIndex, player_id }
    game:player_acted { seatIndex, action, amount?, pot }
    game:phase_changed { phase }
    game:community_cards_revealed { phase, cards }
    game:full_state_sync { gameState }
    game:hand_result  { winners, losers, potBreakdown }
    showdown          HandResult (legacy)
    round-end         (empty — signals hand over)

  Legacy events (still emitted for orchestrator / agent callers):
    your_turn         player view for agent turn protocol
    message           inter-agent message
    nudge_received    human nudge delivered
"""

import asyncio
import logging
from flask import request as flask_request

from app.engine.frontend_adapter import (
    build_frontend_game_state,
    build_hand_result,
    card_to_frontend,
    cards_to_frontend,
    phase_to_frontend,
    action_to_frontend,
)

logger = logging.getLogger(__name__)

_table_store = None
_room_tables: dict[str, str] = {}   # roomCode → table_id
_name_maps: dict[str, dict] = {}    # table_id → { player_id → agent_name }

# Disconnect tracking: sid → { roomCode, userId }
_sid_to_room: dict[str, dict] = {}


def _get_room_store():
    """Lazily import room store to avoid circular imports."""
    from app.routes.rooms import get_room_store
    return get_room_store()


def _emit_room_updated(socketio_ref, room_code: str):
    """Broadcast the current room state to everyone in the socket room."""
    rooms = _get_room_store()
    room = rooms.get(room_code.upper())
    if room:
        socketio_ref.emit("room-updated", room.to_dict(), room=room_code)


def register_socket_events(socketio, table_manager):
    """Register all socket events. Called from app factory."""
    global _table_store
    _table_store = table_manager

    # ── join-room ───────────────────────────────────────────────────────────

    @socketio.on("join-room")
    def handle_join_room(data):
        from flask_socketio import join_room, emit

        room_code = data.get("roomCode", "")
        user_id = data.get("userId", "")
        sid = flask_request.sid

        logger.info("[JOIN-ROOM] room=%s user=%s sid=%s", room_code, user_id[:8] if user_id else "?", sid)

        join_room(room_code)

        # Track this socket for disconnect cleanup
        if sid and user_id:
            _sid_to_room[sid] = {"roomCode": room_code, "userId": user_id}

        # If a game is already in progress, send the game state
        table_id = _room_tables.get(room_code)
        if table_id:
            table = table_manager.get(table_id)
            if table:
                name_map = _name_maps.get(table_id, {})
                state = build_frontend_game_state(
                    table, room_code, name_map=name_map, viewer_id=user_id
                )
                emit("game-state", state)
                return

        # Otherwise send the lobby state
        rooms = _get_room_store()
        room = rooms.get(room_code.upper())
        if room:
            emit("room-updated", room.to_dict())

    # ── leave-room ──────────────────────────────────────────────────────────

    @socketio.on("leave-room")
    def handle_leave_room(data):
        from flask_socketio import leave_room

        room_code = data.get("roomCode", "")
        sid = flask_request.sid
        leave_room(room_code)

        info = _sid_to_room.pop(sid, None)
        if info:
            _remove_player_from_room(socketio, info["roomCode"], info["userId"])

    # ── disconnect ──────────────────────────────────────────────────────────

    @socketio.on("disconnect")
    def handle_disconnect():
        sid = flask_request.sid
        info = _sid_to_room.pop(sid, None)
        if not info:
            return

        room_code = info["roomCode"]
        user_id = info["userId"]
        _remove_player_from_room(socketio, room_code, user_id)

    # ── toggle-ready ────────────────────────────────────────────────────────

    @socketio.on("toggle-ready")
    def handle_toggle_ready(data):
        from flask_socketio import emit

        room_code = data.get("roomCode", "")
        user_id = data.get("userId", "")
        rooms = _get_room_store()
        room = rooms.get(room_code.upper())
        if not room:
            emit("error", {"message": "Room not found."})
            return

        # Find current ready state and toggle
        player = next((p for p in room.players if p.user_id == user_id), None)
        if not player:
            emit("error", {"message": "Player not in room."})
            return

        new_ready = not player.is_ready
        room.set_ready(user_id, new_ready)
        _emit_room_updated(socketio, room_code)

    # ── start-game ──────────────────────────────────────────────────────────

    @socketio.on("start-game")
    def handle_start_game(data):
        from flask_socketio import emit

        room_code = data.get("roomCode", "")
        user_id = data.get("userId", "")
        player_credits = data.get("playerCredits", {})  # { user_id: credits, ... }
        rooms = _get_room_store()
        room = rooms.get(room_code.upper())
        if not room:
            emit("error", {"message": "Room not found."})
            return

        # Only host can start
        host = next((p for p in room.players if p.is_host), None)
        if not host or host.user_id != user_id:
            emit("error", {"message": "Only the host can start the game."})
            return

        # Auto-ready the host when they start the game
        if not host.is_ready:
            room.set_ready(user_id, True)

        if not room.all_ready:
            emit("error", {"message": "Not all players are ready."})
            return

        if len(room.players) < 2:
            emit("error", {"message": "Need at least 2 players."})
            return

        # Create a Table and seat all players
        from app.engine.table import Table
        from app.routes.tables import get_table_store
        from app.config import SMALL_BLIND, BIG_BLIND, STARTING_CHIPS

        table = Table(
            max_seats=room.max_players,
            small_blind=SMALL_BLIND,
            big_blind=BIG_BLIND,
            starting_stack=STARTING_CHIPS,
        )
        get_table_store()[table.id] = table

        # Store initial credit balance for each player to calculate deltas later
        initial_credits = {}
        name_map = {}
        agent_map = {}   # user_id → agent_id (orchestrator key)
        for rp in room.players:
            # Get starting stack for this player from playerCredits, fallback to STARTING_CHIPS
            starting_stack = int(player_credits.get(rp.user_id, STARTING_CHIPS))
            initial_credits[rp.user_id] = starting_stack
            
            result = table.join(
                player_id=rp.user_id,
                player_type="agent",
            )
            # Override the starting stack with the player's credits
            if hasattr(table, 'players') and rp.user_id:
                for p in table.players:
                    if p.player_id == rp.user_id:
                        p.stack = starting_stack
                        break
            name_map[rp.user_id] = rp.agent_name
            agent_map[rp.user_id] = rp.agent_id
        
        # Store initial credits mapping in table for credit delta calculation
        table._initial_credits = initial_credits

        logger.info(
            "[START-GAME] room=%s players=%d name_map=%s agent_map=%s",
            room_code, len(room.players), name_map, agent_map,
        )

        # Bind room to table
        bind_room_to_table(room_code, table.id, name_map)
        room.status = "in-progress"
        room.table_id = table.id

        # Start the first hand
        result = table.start_hand()
        if isinstance(result, str):
            emit("error", {"message": result})
            return

        logger.info(
            "[START-GAME] Hand started: hand_id=%s current_player=%s phase=%s",
            table.current_hand.hand_id if table.current_hand else "?",
            table.current_hand.current_player.player_id[:8] if table.current_hand and table.current_hand.current_player else "?",
            table.current_hand.phase.value if table.current_hand else "?",
        )

        # Broadcast game-started to all in the room
        emit_game_started(socketio, room_code, table, name_map)

        # Start the agent turn loop in a background task
        from app.services.turn_engine import run_turn_loop
        socketio.start_background_task(
            run_turn_loop,
            socketio_ref=socketio,
            room_code=room_code,
            table_id=table.id,
            table=table,
            agent_map=agent_map,
            name_map=name_map,
        )

    # ── join_table (legacy — used by orchestrator / REST callers) ───────────

    @socketio.on("join_table")
    def handle_join_table(data):
        from flask_socketio import join_room, emit
        from app.engine.state_snapshot import build_public_state

        table_id = data.get("table_id")
        player_id = data.get("player_id")
        player_type = data.get("player_type", "human")

        table = table_manager.get(table_id)
        if not table:
            emit("error", {"message": "Table not found."})
            return

        result = table.join(player_id, player_type)
        if isinstance(result, str):
            emit("error", {"message": result})
            return

        join_room(table_id)
        emit("table_state", build_public_state(table), room=table_id)

    # ── player-action (frontend) ────────────────────────────────────────────

    @socketio.on("player-action")
    def handle_player_action(data):
        from flask_socketio import emit

        room_code = data.get("roomCode", "")
        table_id = _room_tables.get(room_code)
        if not table_id:
            emit("error", {"message": "No active game for this room."})
            return

        table = table_manager.get(table_id)
        if not table or not table.current_hand:
            emit("error", {"message": "No active hand."})
            return

        hand = table.current_hand
        seat_index = data.get("seatIndex")
        action_type = data.get("action", "")
        amount = data.get("amount")

        if seat_index is None or seat_index >= len(hand.players):
            emit("error", {"message": "Invalid seat index."})
            return

        player = hand.players[seat_index]
        engine_action = {"type": action_type.replace("-", "_")}
        if amount is not None:
            engine_action["amount"] = amount

        try:
            events = hand.apply_action(player.player_id, engine_action)
        except ValueError as e:
            emit("error", {"message": str(e)})
            return

        name_map = _name_maps.get(table_id, {})
        
        # Process all events and emit them to the room
        for event in events:
            etype = event.get("event")

            if etype == "action":
                next_active = -1
                if hand.current_player:
                    for i, p in enumerate(hand.players):
                        if p.player_id == hand.current_player.player_id:
                            next_active = i
                            break

                emit("game:player_acted", {
                    "seatIndex": seat_index,
                    "action": action_to_frontend(event.get("action_type", "")),
                    "amount": event.get("amount"),
                    "pot": hand.pot,
                    "nextActive": next_active,
                    "playerName": name_map.get(player.player_id, player.player_id),
                }, room=room_code)

            elif etype == "deal_community":
                # Community cards revealed
                emit("game:community_cards_revealed", {
                    "phase": phase_to_frontend(event.get("phase", "")),
                    "cards": cards_to_frontend(hand.community_cards),
                }, room=room_code)

            elif etype == "award_pot":
                # Pot awards are internal, not shown separately
                pass

            elif etype == "hand_complete":
                # Hand complete: emit result with chip changes and credit deltas
                result = build_hand_result(hand, name_map)
                
                # Calculate credit deltas for each player
                credit_deltas = {}
                initial_credits = getattr(table, '_initial_credits', {})
                for player in hand.players:
                    initial = initial_credits.get(player.player_id, 0)
                    delta = player.stack - initial
                    credit_deltas[player.player_id] = delta
                
                # Add credit deltas to result
                result["creditDeltas"] = credit_deltas
                emit("game:hand_result", result, room=room_code)
                
                # Update initial credits for next hand
                for player in hand.players:
                    initial_credits[player.player_id] = player.stack
                
                # Finish the hand and emit round-end
                summary = table.finish_hand()
                emit("round-end", {}, room=room_code)

    # ── action (legacy — used by orchestrator) ──────────────────────────────

    @socketio.on("action")
    def handle_action(data):
        from flask_socketio import emit
        from app.engine.state_snapshot import build_player_view

        table_id = data.get("table_id")
        player_id = data.get("player_id")
        action = data.get("action", {})

        table = table_manager.get(table_id)
        if not table or not table.current_hand:
            emit("error", {"message": "No active hand."})
            return

        try:
            events = table.current_hand.apply_action(player_id, action)
            for event in events:
                emit("action_applied", event, room=table_id)

            if table.current_hand.is_hand_over:
                summary = table.finish_hand()
                if not isinstance(summary, str):
                    emit("hand_completed", summary, room=table_id)
            elif table.current_hand.current_player:
                next_pid = table.current_hand.current_player.player_id
                view = build_player_view(table, next_pid)
                emit("your_turn", view, room=table_id)

        except ValueError as e:
            emit("error", {"message": str(e)})

    # ── send_message / send_nudge (unchanged) ───────────────────────────────

    @socketio.on("send_message")
    def handle_message(data):
        from flask_socketio import emit
        from app.services import communication

        game_id = data.get("game_id")
        sender_id = data.get("sender_id")
        content = data.get("content", "")
        recipient_id = data.get("recipient_id")
        phase = data.get("phase", "between_hands")
        hand_number = data.get("hand_number", 0)

        result = communication.send_message(
            game_id=game_id,
            sender_id=sender_id,
            content=content,
            phase=phase,
            recipient_id=recipient_id,
            current_hand_number=hand_number,
        )

        if isinstance(result, str):
            emit("error", {"message": result})
            return

        if result["is_public"]:
            emit("message", result, room=data.get("table_id"))
        else:
            emit("message", result)

    @socketio.on("send_nudge")
    def handle_nudge(data):
        from flask_socketio import emit
        from app.services import nudges

        result = nudges.send_nudge(
            agent_id=data.get("agent_id"),
            game_id=data.get("game_id"),
            message=data.get("message", ""),
            from_user=data.get("from_user", "anonymous"),
            permission_level=data.get("permission_level", "owner"),
            agent_owner_id=data.get("agent_owner_id"),
        )

        if isinstance(result, str):
            emit("error", {"message": result})
            return

        emit("nudge_received", result)


# ── Disconnect cleanup ──────────────────────────────────────────────────────

def _remove_player_from_room(socketio_ref, room_code: str, user_id: str):
    """Remove a player from a room and auto-delete the room if empty."""
    rooms = _get_room_store()
    room = rooms.get(room_code.upper())
    if not room:
        return

    err = room.remove_player(user_id)
    if err:
        return

    if not room.players:
        # Room is empty — auto-delete it
        rooms.pop(room_code.upper(), None)
        # Also clean up any associated table
        table_id = _room_tables.pop(room_code, None)
        if table_id:
            _name_maps.pop(table_id, None)
            from app.routes.tables import get_table_store
            get_table_store().pop(table_id, None)
        return

    # Room still has players — broadcast the updated state
    _emit_room_updated(socketio_ref, room_code)


# ── Helpers for external callers (routes, game orchestrator) ────────────────

def bind_room_to_table(room_code: str, table_id: str, name_map: dict[str, str] | None = None):
    """Associate a room code with an engine table so socket events route correctly."""
    _room_tables[room_code] = table_id
    if name_map:
        _name_maps[table_id] = name_map


def emit_game_started(socketio_ref, room_code: str, table, name_map: dict[str, str] | None = None):
    """Send per-player game-started events so each player sees their own hole cards."""
    # Build a set of sids in this room with their user_ids
    room_sids: list[tuple[str, str]] = []
    for sid, info in _sid_to_room.items():
        if info["roomCode"] == room_code:
            room_sids.append((sid, info["userId"]))

    if room_sids:
        # Send each player a personalised state with their own cards revealed
        for sid, user_id in room_sids:
            state = build_frontend_game_state(
                table, room_code, name_map=name_map, viewer_id=user_id
            )
            socketio_ref.emit("game-started", state, to=sid)
    else:
        # Fallback: broadcast without viewer (shouldn't happen normally)
        state = build_frontend_game_state(table, room_code, name_map=name_map)
        socketio_ref.emit("game-started", state, room=room_code)


def emit_turn_to_agent(socketio_ref, table_id: str, table, player_id: str):
    """Helper to emit a your_turn event for an agent player."""
    from app.engine.state_snapshot import build_player_view
    view = build_player_view(table, player_id)
    socketio_ref.emit("your_turn", view, room=table_id)


def emit_hand_start(socketio_ref, table_id: str, table):
    """Broadcast hand_started to all in the room."""
    from app.engine.state_snapshot import build_public_state
    socketio_ref.emit("hand_started", build_public_state(table), room=table_id)


def emit_player_thinking(socketio_ref, room_code: str, table_id: str, seat_index: int, player_id: str):
    """Emit thinking indicator event when player is about to be asked for action."""
    # Delay a bit so UI has time to show the bubble
    socketio_ref.emit("game:player_thinking", {
        "seatIndex": seat_index,
        "player_id": player_id,
    }, room=room_code, skip_sid=True)


def emit_phase_changed(socketio_ref, room_code: str, phase: str):
    """Emit explicit phase transition event."""
    socketio_ref.emit("game:phase_changed", {
        "phase": phase_to_frontend(phase),
    }, room=room_code, skip_sid=True)


def emit_full_state_sync(socketio_ref, room_code: str, table, name_map: dict[str, str] | None = None):
    """Emit full game state snapshot for synchronization (per-player with cards)."""
    room_sids: list[tuple[str, str]] = []
    for sid, info in _sid_to_room.items():
        if info["roomCode"] == room_code:
            room_sids.append((sid, info["userId"]))

    if room_sids:
        for sid, user_id in room_sids:
            state = build_frontend_game_state(
                table, room_code, name_map=name_map, viewer_id=user_id
            )
            socketio_ref.emit("game:full_state_sync", state, to=sid)
    else:
        state = build_frontend_game_state(table, room_code, name_map=name_map)
        socketio_ref.emit("game:full_state_sync", state, room=room_code)
