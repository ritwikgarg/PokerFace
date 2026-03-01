from __future__ import annotations

"""
Agent turn engine — drives the auto-play loop for AI-vs-AI games.

After a hand is dealt, this module runs each agent's turn sequentially:
  1. Build game state for the current player
  2. Assemble prompt (personality + memory + history)
  3. Call Modal inference (or fallback)
  4. Parse and validate the action
  5. Apply to the engine
  6. Emit socket events to all clients
  7. Repeat until hand is complete

All operations are logged extensively for debugging.
"""

import logging
import os
import sys
import time
import traceback

# Use eventlet-native timeout on Render, ThreadPoolExecutor locally
_USE_EVENTLET = bool(os.environ.get("RENDER"))
if _USE_EVENTLET:
    try:
        import eventlet
        from eventlet.timeout import Timeout as EventletTimeout
    except ImportError:
        _USE_EVENTLET = False

if not _USE_EVENTLET:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.config import SUPPORTED_MODELS, resolve_frontend_model
from app.engine.state_snapshot import build_game_state_for_orchestrator
from app.engine.frontend_adapter import (
    build_hand_result,
    cards_to_frontend,
    phase_to_frontend,
    action_to_frontend,
)
from app.services import orchestrator
from app.services.game_state import build_inference_request, parse_action
from app.services import memory as memory_svc
from app.services import modal_workers
from app.services import supermemory
from app.services import communication
from app.services.security import validate_action_schema, sanitize_response
from app.services.table_talk import filter_table_talk
from app.services import file_logger
from app.services import logging_service

logger = logging.getLogger(__name__)

# ── Timeout configuration ───────────────────────────────────────────────────
FIRST_TURN_TIMEOUT_SECS = 20   # 20 seconds for all turns
TURN_TIMEOUT_SECS = 20         # 20 seconds for all turns
DEFAULT_TIMEOUT_ACTION = {"type": "call"}  # fallback when timeout fires


def run_turn_loop(
    socketio_ref,
    room_code: str,
    table_id: str,
    table,
    agent_map: dict[str, str],
    name_map: dict[str, str],
):
    """
    Drive the agent turn loop for a hand. Runs in a background thread.

    Args:
        socketio_ref: Flask-SocketIO instance for emitting events
        room_code: The room code for socket room targeting
        table_id: Engine table ID
        table: Table object
        agent_map: user_id → agent_id (orchestrator key)
        name_map: user_id → agent display name
    """
    hand = table.current_hand
    if not hand:
        logger.error("[TURN-LOOP] room=%s — No current hand, aborting", room_code)
        return

    logger.info(
        "[TURN-LOOP] ▶ Starting for room=%s table=%s hand=%s players=%d",
        room_code, table_id, hand.hand_id, len(hand.players),
    )
    logger.info(
        "[TURN-LOOP]   agent_map=%s  name_map=%s",
        agent_map, name_map,
    )

    turn_count = 0
    MAX_TURNS = 100  # Safety limit to prevent infinite loops

    while not hand.is_hand_over and turn_count < MAX_TURNS:
        current = hand.current_player
        if not current:
            logger.info("[TURN-LOOP] No current player — hand phase=%s", hand.phase.value)
            break

        player_id = current.player_id
        agent_id = agent_map.get(player_id)
        seat_index = _find_seat_index(hand, player_id)
        turn_count += 1

        # First turn gets extra time for Modal cold-start, rest get 30s
        timeout = FIRST_TURN_TIMEOUT_SECS if turn_count == 1 else TURN_TIMEOUT_SECS

        logger.info(
            "[TURN-LOOP] ── Turn %d: player=%s agent=%s seat=%d phase=%s timeout=%ds",
            turn_count, player_id[:8], agent_id[:8] if agent_id else "?",
            seat_index, hand.phase.value, timeout,
        )
        sys.stdout.flush()

        # Small delay so the UI can show progression
        socketio_ref.sleep(1.0)

        # Emit thinking indicator
        _emit_thinking(socketio_ref, room_code, seat_index, player_id)

        # Execute the turn WITH TIMEOUT
        try:
            action = _execute_with_timeout(
                timeout_secs=timeout,
                agent_id=agent_id,
                player_id=player_id,
                table_id=table_id,
                table=table,
                name_map=name_map,
            )
        except Exception:
            logger.exception("[TURN-LOOP] Error executing turn for player=%s", player_id[:8])
            action = DEFAULT_TIMEOUT_ACTION.copy()

        logger.info("[TURN-LOOP]   → Action: %s", action)

        # Apply the action to the engine
        try:
            events = hand.apply_action(player_id, action)
        except ValueError as e:
            logger.warning(
                "[TURN-LOOP]   Action rejected: %s — falling back to fold", e,
            )
            try:
                events = hand.apply_action(player_id, {"type": "fold"})
            except ValueError:
                logger.error("[TURN-LOOP]   Even fold rejected — breaking loop")
                break

        # Emit events to all clients
        _process_events(
            socketio_ref, room_code, table, hand, events,
            seat_index, player_id, name_map,
        )

        # Brief pause between turns for UI readability
        socketio_ref.sleep(0.5)

    if turn_count >= MAX_TURNS:
        logger.error("[TURN-LOOP] ⚠ Hit MAX_TURNS (%d) for room=%s", MAX_TURNS, room_code)

    logger.info("[TURN-LOOP] ◼ Loop complete for room=%s, turns=%d", room_code, turn_count)
    sys.stdout.flush()


# ── Timeout wrapper ─────────────────────────────────────────────────────────

if not _USE_EVENTLET:
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="turn-exec")


def _execute_with_timeout(
    timeout_secs: int,
    agent_id: str | None,
    player_id: str,
    table_id: str,
    table,
    name_map: dict[str, str],
) -> dict:
    """
    Run _execute_single_turn with a hard timeout.
    If the model doesn't respond in time, returns DEFAULT_TIMEOUT_ACTION (call).

    Uses eventlet.Timeout on Render (green-thread safe) or
    ThreadPoolExecutor locally (real-thread safe).
    """
    if _USE_EVENTLET:
        return _execute_with_eventlet_timeout(
            timeout_secs, agent_id, player_id, table_id, table, name_map,
        )
    else:
        return _execute_with_thread_timeout(
            timeout_secs, agent_id, player_id, table_id, table, name_map,
        )


def _execute_with_eventlet_timeout(
    timeout_secs, agent_id, player_id, table_id, table, name_map,
) -> dict:
    """Eventlet-native timeout — safe for green threads."""
    try:
        with EventletTimeout(timeout_secs):
            return _execute_single_turn(
                agent_id=agent_id,
                player_id=player_id,
                table_id=table_id,
                table=table,
                name_map=name_map,
            )
    except EventletTimeout:
        logger.warning(
            "[TURN-TIMEOUT] ⏱ Player=%s timed out after %ds — defaulting to call",
            player_id[:8], timeout_secs,
        )
        sys.stdout.flush()
        return DEFAULT_TIMEOUT_ACTION.copy()
    except Exception:
        logger.exception(
            "[TURN-TIMEOUT] Exception during turn for player=%s", player_id[:8],
        )
        sys.stdout.flush()
        return DEFAULT_TIMEOUT_ACTION.copy()


def _execute_with_thread_timeout(
    timeout_secs, agent_id, player_id, table_id, table, name_map,
) -> dict:
    """ThreadPoolExecutor timeout — for local dev (threading mode)."""
    future = _executor.submit(
        _execute_single_turn,
        agent_id=agent_id,
        player_id=player_id,
        table_id=table_id,
        table=table,
        name_map=name_map,
    )

    try:
        result = future.result(timeout=timeout_secs)
        return result
    except FuturesTimeoutError:
        logger.warning(
            "[TURN-TIMEOUT] ⏱ Player=%s timed out after %ds — defaulting to call",
            player_id[:8], timeout_secs,
        )
        sys.stdout.flush()
        future.cancel()
        return DEFAULT_TIMEOUT_ACTION.copy()
    except Exception:
        logger.exception(
            "[TURN-TIMEOUT] Exception during turn for player=%s", player_id[:8],
        )
        sys.stdout.flush()
        return DEFAULT_TIMEOUT_ACTION.copy()


# ── Single turn execution ───────────────────────────────────────────────────

def _execute_single_turn(
    agent_id: str | None,
    player_id: str,
    table_id: str,
    table,
    name_map: dict[str, str],
) -> dict:
    """
    Execute one agent's turn: build prompt → inference → parse → return action.
    Returns an engine-compatible action dict like {"type": "call"} or {"type": "raise", "amount": 100}.
    """
    # Get the agent config from the orchestrator
    agent = orchestrator.get_agent(agent_id) if agent_id else None
    if not agent:
        logger.warning(
            "[TURN] Agent not found for agent_id=%s (player=%s) — defaulting to call",
            agent_id, player_id[:8],
        )
        return {"type": "call"}

    # Build game state in orchestrator format
    game_state = build_game_state_for_orchestrator(table, player_id)
    if not game_state:
        logger.warning("[TURN] Could not build game_state for player=%s — defaulting to call", player_id[:8])
        return {"type": "call"}

    hand_id = game_state.get("hand_id", "unknown")
    game_id = table_id

    logger.info(
        "[TURN] Player=%s (%s) | model=%s | phase=%s | pot=%d | stack=%d",
        player_id[:8], agent.name, agent.resolved_model,
        game_state.get("round"), game_state.get("pot"), game_state.get("player_stack"),
    )
    sys.stdout.flush()

    # Step 1: Assemble prompt with memory
    assembled = orchestrator.assemble_prompt(agent)
    agent_memory = memory_svc.get_or_create(agent_id, game_id)

    # Fetch long-term memory from Supermemory
    opponent_ids = [o.get("id", str(o)) for o in game_state.get("opponent_stacks", [])]
    street = game_state.get("round", "preflop")
    board = game_state.get("community_cards", [])
    try:
        long_term_ctx = supermemory.get_decision_context(
            agent_id, opponent_ids, street, board,
            history_level=agent.previous_games_history,
        )
    except Exception:
        logger.warning("[TURN] Supermemory lookup failed for agent=%s", agent.name, exc_info=True)
        long_term_ctx = ""

    memory_context = agent_memory.build_memory_context(long_term_context=long_term_ctx)
    if memory_context:
        assembled["assembled_system_prompt"] += f"\n\n{memory_context}"

    # Inject visible messages
    try:
        visible_messages = communication.get_messages_for_player(game_id, agent_id)
        if visible_messages:
            msg_lines = []
            for m in visible_messages[-5:]:
                sender = orchestrator.get_agent(m["sender_id"])
                sender_name = sender.name if sender else m["sender_id"][:8]
                msg_lines.append(f"[{sender_name}]: {m['content']}")
            assembled["assembled_system_prompt"] += "\n\n=== Table Chat ===\n" + "\n".join(msg_lines)
    except Exception:
        pass

    inference_req = build_inference_request(assembled, game_state)

    # File log: turn start
    file_logger.log_turn_start(game_id, agent_id, agent.name, hand_id, game_state.get("round", "?"))

    # Step 2: Call Modal worker for inference
    resolved = agent.resolved_model
    model_meta = SUPPORTED_MODELS.get(resolved, {})

    logger.info("[TURN] Calling inference: model=%s type=%s", resolved, model_meta.get("type", "unknown"))
    sys.stdout.flush()

    t0 = time.perf_counter()
    try:
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
    except Exception:
        logger.exception("[TURN] Inference call failed for agent=%s", agent.name)
        result = {
            "raw_response": '{"action": "call", "reasoning": "Inference error, defaulting to call."}',
            "latency_ms": 0,
            "tokens_used": 0,
            "stub": True,
        }

    inference_ms = (time.perf_counter() - t0) * 1000
    raw_response = sanitize_response(result.get("raw_response", ""))

    logger.info(
        "[TURN] Inference result: latency=%.0fms stub=%s raw=%s",
        inference_ms, result.get("stub"), raw_response[:200],
    )
    if result.get("error"):
        logger.warning("[TURN] Inference error: %s", result.get("error"))
    sys.stdout.flush()

    # File log: prompt details
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

    schema_ok, schema_err = validate_action_schema(parsed)
    if not schema_ok:
        logger.warning("[TURN] Schema validation failed: %s", schema_err)
        logging_service.log_failure(agent_id, game_id, hand_id, "invalid_json", schema_err, raw_response)
        parsed = {
            "action": "fold", "type": "fold", "amount": None,
            "reasoning": f"Schema error: {schema_err}", "parse_ok": False,
        }

    logger.info(
        "[TURN] Parsed action: %s amount=%s parse_ok=%s",
        parsed.get("action"), parsed.get("amount"), parsed.get("parse_ok"),
    )
    sys.stdout.flush()

    # Handle table talk
    raw_talk = parsed.pop("table_talk", None)
    filtered_talk = filter_table_talk(raw_talk or "", agent.name) if raw_talk else None

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

    # Update memory
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

    # Supermemory persistence (non-blocking best-effort)
    try:
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
    except Exception:
        logger.debug("[TURN] Supermemory store failed", exc_info=True)

    # Logging service
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

    # Build the engine action
    action_type = parsed.get("action", "fold")
    engine_action = {"type": action_type.replace("-", "_")}
    if parsed.get("amount") is not None:
        engine_action["amount"] = parsed["amount"]

    return engine_action


# ── Event processing (mirrors handle_player_action logic) ───────────────────

def _process_events(
    socketio_ref,
    room_code: str,
    table,
    hand,
    events: list[dict],
    seat_index: int,
    player_id: str,
    name_map: dict[str, str],
):
    """Process engine events and emit them to the frontend via Socket.IO."""
    for event in events:
        etype = event.get("event")

        if etype == "action":
            next_active = -1
            if hand.current_player:
                for i, p in enumerate(hand.players):
                    if p.player_id == hand.current_player.player_id:
                        next_active = i
                        break

            socketio_ref.emit("game:player_acted", {
                "seatIndex": seat_index,
                "action": action_to_frontend(event.get("action_type", "")),
                "amount": event.get("amount"),
                "pot": hand.pot,
                "nextActive": next_active,
                "playerName": name_map.get(player_id, player_id[:8]),
            }, room=room_code)

            logger.info(
                "[EVENTS] player_acted seat=%d action=%s amount=%s pot=%d next=%d",
                seat_index, event.get("action_type"), event.get("amount"),
                hand.pot, next_active,
            )

        elif etype == "deal_community":
            socketio_ref.emit("game:community_cards_revealed", {
                "phase": phase_to_frontend(event.get("phase", "")),
                "cards": cards_to_frontend(hand.community_cards),
            }, room=room_code)

            logger.info(
                "[EVENTS] community_cards phase=%s cards=%d",
                event.get("phase"), len(hand.community_cards),
            )

        elif etype == "award_pot":
            logger.info("[EVENTS] award_pot player=%s amount=%s", event.get("player_id"), event.get("amount"))

        elif etype == "hand_complete":
            result = build_hand_result(hand, name_map)

            # Calculate credit deltas
            credit_deltas = {}
            initial_credits = getattr(table, '_initial_credits', {})
            for player in hand.players:
                initial = initial_credits.get(player.player_id, 0)
                delta = player.stack - initial
                credit_deltas[player.player_id] = delta

            result["creditDeltas"] = credit_deltas
            socketio_ref.emit("game:hand_result", result, room=room_code)

            logger.info(
                "[EVENTS] hand_complete winner=%s pot=%s deltas=%s",
                result.get("winnerUserId", "?")[:8],
                result.get("potWon"),
                credit_deltas,
            )

            # Update initial credits for next hand
            for player in hand.players:
                initial_credits[player.player_id] = player.stack

            # Finish the hand
            summary = table.finish_hand()
            socketio_ref.emit("round-end", {}, room=room_code)

            logger.info("[EVENTS] round-end emitted for room=%s", room_code)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _find_seat_index(hand, player_id: str) -> int:
    for i, p in enumerate(hand.players):
        if p.player_id == player_id:
            return i
    return -1


def _emit_thinking(socketio_ref, room_code: str, seat_index: int, player_id: str):
    socketio_ref.emit("game:player_thinking", {
        "seatIndex": seat_index,
        "player_id": player_id,
    }, room=room_code)
