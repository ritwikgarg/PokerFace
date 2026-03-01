from __future__ import annotations

"""
Full turn protocol: bridges the game engine, orchestrator, memory, modal
workers, communication, nudges, logging, and security into a single flow.

Primary endpoints:
  POST /api/game/turn            — full turn: engine state → prompt → inference → action
  POST /api/game/build-prompt    — step 1 only: build inference request (with memory)
  POST /api/game/parse-action    — step 3 only: parse raw LLM response
  POST /api/game/messages        — inter-agent messaging
  POST /api/game/nudge           — human nudge
  GET  /api/game/logs            — decision and failure logs
"""

from flask import Blueprint, request, jsonify

from app.services import orchestrator
from app.services.game_state import build_inference_request, build_user_message, parse_action
from app.services import memory as memory_svc
from app.services import modal_workers
from app.services import communication
from app.services import nudges
from app.services import logging_service
from app.services import supermemory
from app.services.security import validate_action_schema, check_rate_limit, sanitize_response
from app.services.table_talk import filter_table_talk
from app.services import file_logger
from app.engine.state_snapshot import build_game_state_for_orchestrator
from app.config import SUPPORTED_MODELS, resolve_frontend_model

game_bp = Blueprint("game", __name__)


@game_bp.route("/game/turn", methods=["POST"])
def full_turn():
    """
    Execute a complete agent turn:
      1. Get table state from engine (passed in or looked up)
      2. Build prompt with memory + personality + risk
      3. Call Modal worker for inference
      4. Parse and validate action
      5. Log everything
      6. Return validated action for engine to apply

    Body:
    {
      "agent_id": "uuid",
      "table_id": "uuid",
      "game_state": { ... },     // optional: if not provided, built from table
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    agent_id = data.get("agent_id")
    table_id = data.get("table_id")
    game_state = data.get("game_state")

    if not agent_id:
        return jsonify({"error": "'agent_id' is required."}), 422

    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    # Rate limit check
    allowed, err = check_rate_limit(agent_id)
    if not allowed:
        return jsonify({"error": err}), 429

    # If no game_state provided and table_id given, build from engine
    if not game_state and table_id:
        from app.routes.tables import get_table_store
        table = get_table_store().get(table_id)
        if table and table.current_hand:
            game_state = build_game_state_for_orchestrator(table, agent_id)

    if not game_state:
        return jsonify({"error": "No game_state provided and could not build from table."}), 422

    game_id = table_id or "unknown"
    hand_id = game_state.get("hand_id", "unknown")

    # Step 1: Assemble prompt with memory
    assembled = orchestrator.assemble_prompt(agent)
    agent_memory = memory_svc.get_or_create(agent_id, game_id)

    # Fetch long-term memory from Supermemory based on agent's history level
    opponent_ids = [o.get("id", str(o)) for o in game_state.get("opponent_stacks", [])]
    street = game_state.get("round", "preflop")
    board = game_state.get("community_cards", [])
    long_term_ctx = supermemory.get_decision_context(
        agent_id, opponent_ids, street, board,
        history_level=agent.previous_games_history,
    )

    memory_context = agent_memory.build_memory_context(long_term_context=long_term_ctx)

    # Inject memory into system prompt
    if memory_context:
        assembled["assembled_system_prompt"] += f"\n\n{memory_context}"

    # Inject visible messages with agent names instead of raw UUIDs
    visible_messages = communication.get_messages_for_player(game_id, agent_id)
    if visible_messages:
        msg_lines = []
        for m in visible_messages[-5:]:
            sender = orchestrator.get_agent(m["sender_id"])
            name = sender.name if sender else m["sender_id"][:8]
            msg_lines.append(f"[{name}]: {m['content']}")
        assembled["assembled_system_prompt"] += "\n\n=== Table Chat ===\n" + "\n".join(msg_lines)

    inference_req = build_inference_request(assembled, game_state)
    
    # Emit thinking indicator to frontend (before LLM call)
    try:
        from flask_socketio import SocketIO
        from app.sockets.table_namespace import emit_player_thinking
        from app.routes.tables import get_table_store
        
        # Find the room code and seat index for this player
        table = get_table_store().get(table_id) if table_id else None
        if table and table.current_hand:
            # Find player's seat
            for seat_idx, player in enumerate(table.current_hand.players):
                if player.player_id == agent_id:
                    # Find room code from table
                    from app.sockets.table_namespace import _room_tables
                    room_code = None
                    for room, t_id in _room_tables.items():
                        if t_id == table_id:
                            room_code = room
                            break
                    
                    if room_code:
                        # Import the global socketio instance
                        from app import socketio
                        emit_player_thinking(socketio, room_code, table_id, seat_idx, agent_id)
                    break
    except Exception:
        # If thinking emission fails, don't block the main flow
        pass

    # File log: turn start
    file_logger.log_turn_start(game_id, agent_id, agent.name, hand_id, game_state.get("round", "?"))

    # Step 2: Call Modal worker
    resolved = agent.resolved_model
    model_meta = SUPPORTED_MODELS.get(resolved, {})
    with logging_service.Timer() as timer:
        if model_meta.get("type") == "open_source":
            worker = modal_workers.get_or_create_worker(
                model_key=resolved,
                hf_repo_id=model_meta.get("hf_repo_id", ""),
                gpu=model_meta.get("recommended_gpu", "T4"),
                table_id=game_id,
            )
            result = modal_workers.call_inference(
                worker,
                messages=inference_req["messages"],
                temperature=inference_req["temperature"],
            )
        else:
            result = {
                "raw_response": '{"action": "fold", "reasoning": "API models not connected."}',
                "latency_ms": 0,
                "tokens_used": 0,
                "stub": True,
            }

    inference_ms = timer.elapsed_ms
    raw_response = sanitize_response(result.get("raw_response", ""))

    # File log: full prompt that was injected into the model
    file_logger.log_prompt(
        game_id=game_id,
        agent_id=agent_id,
        agent_name=agent.name,
        hand_id=hand_id,
        phase=game_state.get("round", "?"),
        system_prompt=inference_req["messages"][0]["content"],
        user_message=inference_req["messages"][1]["content"],
        game_state=game_state,
        raw_response=raw_response,
    )

    # Step 3: Parse and validate action
    legal_actions = game_state.get("legal_actions", [])
    parsed = parse_action(raw_response, legal_actions)

    # Security: strict schema check
    schema_ok, schema_err = validate_action_schema(parsed)
    if not schema_ok:
        logging_service.log_failure(agent_id, game_id, hand_id, "invalid_json", schema_err, raw_response)
        parsed = {"action": "fold", "type": "fold", "amount": None, "reasoning": f"Schema error: {schema_err}", "parse_ok": False}

    # Step 4: Table talk — filter, store, and broadcast via socket
    raw_talk = parsed.pop("table_talk", None)
    filtered_talk = filter_table_talk(raw_talk or "", agent.name) if raw_talk else None
    if filtered_talk:
        msg = communication.send_message(
            game_id=game_id,
            sender_id=agent_id,
            content=filtered_talk,
            phase="on_your_turn",
            recipient_id=None,
            current_hand_number=game_state.get("hand_number", 0),
        )
        if isinstance(msg, dict):
            from app import socketio
            socketio.emit("table-talk", {
                "agentId": agent_id,
                "agentName": agent.name,
                "message": filtered_talk,
                "action": parsed.get("action", "fold"),
                "timestamp": msg.get("timestamp", ""),
            }, room=table_id)

    # File log: turn result
    file_logger.log_turn_result(
        game_id=game_id,
        agent_name=agent.name,
        action={"type": parsed.get("action", "fold"), "amount": parsed.get("amount")},
        reasoning=parsed.get("reasoning", ""),
        table_talk=filtered_talk,
        inference_ms=inference_ms,
        parse_ok=parsed.get("parse_ok", False),
    )

    # Step 5: Log and update memory
    reasoning = parsed.get("reasoning", "")
    memory_update = parsed.get("memory_update")

    agent_memory.add_reasoning_trace(hand_id, parsed, reasoning, memory_update)

    hand_number = game_state.get("hand_number")
    hole_cards = game_state.get("hole_cards", [])
    community_cards = game_state.get("community_cards", [])
    summary_line = (
        f"Hand {hand_id}: I held {' '.join(hole_cards)} "
        f"with board {' '.join(community_cards)}. "
        f"Action: {parsed.get('action')}. Reason: {reasoning[:100]}"
    )
    agent_memory.add_summary(summary_line, hand_number)

    # Persist to Supermemory (non-blocking, best-effort)
    action_str = f"{parsed.get('action', 'fold')}"
    if parsed.get("amount"):
        action_str += f" {parsed['amount']}"
    supermemory.summarize_and_store(
        game_id=game_id,
        agent_id=agent_id,
        hand_id=hand_id,
        hole_cards=hole_cards,
        board=community_cards,
        position=game_state.get("position", "?"),
        actions=[action_str],
        result=f"action taken: {action_str}",
        pot_size=game_state.get("pot", 0),
        opponents=[str(o.get("id", o)) for o in game_state.get("opponent_stacks", [])],
    )

    logging_service.log_decision(
        agent_id=agent_id,
        game_id=game_id,
        hand_id=hand_id,
        action=parsed,
        reasoning=reasoning,
        memory_update=memory_update,
        inference_latency_ms=inference_ms,
        parse_ok=parsed.get("parse_ok", False),
    )

    if not parsed.get("parse_ok"):
        logging_service.log_failure(
            agent_id=agent_id, game_id=game_id, hand_id=hand_id,
            failure_type="invalid_json" if not parsed.get("parse_ok") else "illegal_action",
            details=parsed.get("reasoning", ""),
            raw_response=raw_response,
        )

    # Return validated action for the engine
    response = {
        "action": {"type": parsed.get("action", "fold"), "amount": parsed.get("amount")},
        "parse_ok": parsed.get("parse_ok", False),
        "reasoning": reasoning,
        "inference_latency_ms": round(inference_ms, 1),
        "stub": result.get("stub", False),
    }
    if filtered_talk:
        response["table_talk"] = filtered_talk
    return jsonify(response)


@game_bp.route("/game/build-prompt", methods=["POST"])
def build_prompt():
    """Build inference request with memory context (step 1 of turn protocol)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    agent_id = data.get("agent_id")
    game_state = data.get("game_state")
    game_id = data.get("game_id", "unknown")

    if not agent_id:
        return jsonify({"error": "'agent_id' is required."}), 422
    if not game_state or not isinstance(game_state, dict):
        return jsonify({"error": "'game_state' must be a JSON object."}), 422

    agent = orchestrator.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found."}), 404

    assembled = orchestrator.assemble_prompt(agent)

    # Inject memory
    agent_memory = memory_svc.get_or_create(agent_id, game_id)
    memory_context = agent_memory.build_memory_context()
    if memory_context:
        assembled["assembled_system_prompt"] += f"\n\n{memory_context}"

    inference_request = build_inference_request(assembled, game_state)
    return jsonify(inference_request)


@game_bp.route("/game/parse-action", methods=["POST"])
def parse_agent_action():
    """Parse raw LLM response into a validated poker action (step 3 of turn protocol)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    raw = sanitize_response(data.get("raw_response", ""))
    legal = data.get("legal_actions", [])

    if not legal:
        return jsonify({"error": "'legal_actions' is required."}), 422

    result = parse_action(raw, legal)
    return jsonify(result)


@game_bp.route("/game/messages", methods=["POST"])
def send_inter_agent_message():
    """Send an inter-agent message (mediated by orchestrator)."""
    data = request.get_json(silent=True) or {}
    result = communication.send_message(
        game_id=data.get("game_id", ""),
        sender_id=data.get("sender_id", ""),
        content=data.get("content", ""),
        phase=data.get("phase", "between_hands"),
        recipient_id=data.get("recipient_id"),
        current_hand_number=data.get("hand_number", 0),
        communication_enabled=data.get("communication_enabled", True),
    )
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result), 201


@game_bp.route("/game/messages/<game_id>", methods=["GET"])
def get_messages(game_id: str):
    player_id = request.args.get("player_id")
    if player_id:
        msgs = communication.get_messages_for_player(game_id, player_id)
    else:
        msgs = communication.get_public_messages(game_id)
    return jsonify(msgs)


@game_bp.route("/game/nudge", methods=["POST"])
def send_human_nudge():
    """Send a human nudge to an agent."""
    data = request.get_json(silent=True) or {}
    result = nudges.send_nudge(
        agent_id=data.get("agent_id", ""),
        game_id=data.get("game_id", ""),
        message=data.get("message", ""),
        from_user=data.get("from_user", "anonymous"),
        permission_level=data.get("permission_level", "owner"),
        agent_owner_id=data.get("agent_owner_id"),
    )
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    return jsonify(result), 201


@game_bp.route("/game/nudges/<game_id>", methods=["GET"])
def get_nudges(game_id: str):
    agent_id = request.args.get("agent_id")
    if agent_id:
        return jsonify(nudges.get_nudges(agent_id, game_id))
    return jsonify(nudges.get_all_nudges(game_id))


@game_bp.route("/game/logs/<game_id>", methods=["GET"])
def get_game_logs(game_id: str):
    return jsonify({
        "decisions": logging_service.get_decisions(game_id=game_id),
        "failures": logging_service.get_failures(game_id=game_id),
        "timings": logging_service.get_timings(game_id=game_id),
        "stats": logging_service.get_game_stats(game_id),
    })


@game_bp.route("/game/workers", methods=["GET"])
def get_workers():
    table_id = request.args.get("table_id")
    workers = modal_workers.list_workers(table_id)
    return jsonify({
        "workers": [w.to_dict() for w in workers],
        "health": modal_workers.health_check(),
    })
