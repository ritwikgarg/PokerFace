from __future__ import annotations

"""
File-based game logging.

Writes two log files per game into backend/logs/:
  1. game_<id>.log    — full run output (turns, actions, results, table talk)
  2. prompts_<id>.log — exact system prompt + user message injected into the model each turn

Both files are human-readable and append-only during a game.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _short_id(uid: str) -> str:
    return uid[:8] if uid else "?"


# ── Game log (run output) ───────────────────────────────────────────────────

def log_game_event(game_id: str, event_type: str, data: dict):
    path = LOGS_DIR / f"game_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"[{_ts()}] {event_type}\n")
        f.write(f"{'='*70}\n")
        f.write(json.dumps(data, indent=2, default=str))
        f.write("\n")


def log_turn_start(game_id: str, agent_id: str, agent_name: str, hand_id: str, phase: str):
    path = LOGS_DIR / f"game_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        f.write(f"\n{'─'*70}\n")
        f.write(f"[{_ts()}] TURN: {agent_name} ({_short_id(agent_id)})\n")
        f.write(f"  Hand: {_short_id(hand_id)}  Phase: {phase}\n")
        f.write(f"{'─'*70}\n")


def log_turn_result(
    game_id: str,
    agent_name: str,
    action: dict,
    reasoning: str,
    table_talk: str | None,
    inference_ms: float,
    parse_ok: bool,
):
    path = LOGS_DIR / f"game_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        action_str = action.get("type", action.get("action", "?"))
        amount = action.get("amount")
        if amount:
            action_str += f" {amount}"

        f.write(f"  Action:    {action_str}\n")
        f.write(f"  Reasoning: {reasoning}\n")
        if table_talk:
            f.write(f"  Talk:      \"{table_talk}\"\n")
        f.write(f"  Latency:   {inference_ms:.0f}ms  Parse OK: {parse_ok}\n")


def log_hand_result(game_id: str, summary: dict):
    path = LOGS_DIR / f"game_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        f.write(f"\n{'*'*70}\n")
        f.write(f"[{_ts()}] HAND COMPLETE\n")
        f.write(f"{'*'*70}\n")

        winners = summary.get("winners", [])
        for w in winners:
            f.write(f"  Winner: {_short_id(w['player_id'])} — {w.get('hand_rank', '?')}"
                    f" — won {w.get('amount', 0)} chips\n")
            cards = w.get("cards", [])
            if cards:
                f.write(f"  Cards:  {' '.join(cards)}\n")

        community = summary.get("community_cards", [])
        if community:
            f.write(f"  Board:  {' '.join(community)}\n")

        f.write(f"  Pot:    {summary.get('pot', 0)}\n")

        results = summary.get("player_results", {})
        for pid, res in results.items():
            f.write(f"  {_short_id(pid)}: stack {res.get('final_stack', '?')}"
                    f" (delta {res.get('delta', '?'):+d})"
                    f"{'  [folded]' if res.get('folded') else ''}\n")


def log_table_talk_summary(game_id: str, messages: list[dict], agent_names: dict):
    path = LOGS_DIR / f"game_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"TABLE TALK LOG\n")
        f.write(f"{'='*70}\n")
        for m in messages:
            name = agent_names.get(m.get("sender_id", ""), _short_id(m.get("sender_id", "")))
            f.write(f"  [{name}]: \"{m.get('content', '')}\"\n")


# ── Prompt log (what was injected into the model) ───────────────────────────

def log_prompt(
    game_id: str,
    agent_id: str,
    agent_name: str,
    hand_id: str,
    phase: str,
    system_prompt: str,
    user_message: str,
    game_state: dict,
    raw_response: str,
):
    path = LOGS_DIR / f"prompts_{_short_id(game_id)}.log"
    with open(path, "a") as f:
        f.write(f"\n{'#'*70}\n")
        f.write(f"[{_ts()}] {agent_name} ({_short_id(agent_id)})\n")
        f.write(f"Hand: {_short_id(hand_id)}  Phase: {phase}\n")
        f.write(f"{'#'*70}\n\n")

        f.write(f"── SYSTEM PROMPT ({len(system_prompt)} chars) ──\n")
        f.write(system_prompt)
        f.write("\n\n")

        f.write(f"── USER MESSAGE ({len(user_message)} chars) ──\n")
        f.write(user_message)
        f.write("\n\n")

        f.write(f"── GAME STATE ──\n")
        state_summary = {
            "round": game_state.get("round"),
            "hole_cards": game_state.get("hole_cards"),
            "community_cards": game_state.get("community_cards"),
            "pot": game_state.get("pot"),
            "current_bet": game_state.get("current_bet"),
            "player_stack": game_state.get("player_stack"),
            "position": game_state.get("position"),
            "legal_actions": game_state.get("legal_actions"),
            "hand_action_history": game_state.get("hand_action_history"),
        }
        f.write(json.dumps(state_summary, indent=2, default=str))
        f.write("\n\n")

        f.write(f"── RAW MODEL RESPONSE ──\n")
        f.write(raw_response)
        f.write("\n")
