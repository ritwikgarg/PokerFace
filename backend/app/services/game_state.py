from __future__ import annotations

"""
Agent call protocol: translates game engine state into LLM prompts
and parses LLM responses back into validated poker actions.

This is the contract between the game engine, the orchestrator, and
the inference layer. The game engine sends state, the orchestrator
builds the prompt, inference gets a response, and this module parses
it back into a legal action.

── Inbound (from game engine) ──────────────────────────────────────
{
  "hand_id": "abc-123",
  "round": "flop",                       # preflop | flop | turn | river
  "player_id": 1,
  "hole_cards": ["Ah", "Kd"],
  "community_cards": ["7s", "8d", "Jc"],
  "pot": 350,
  "current_bet": 100,
  "player_stack": 1450,
  "opponent_stacks": [{"id": 2, "stack": 980}, ...],
  "position": "BTN",                     # SB | BB | UTG | MP | CO | BTN
  "betting_history": [
    {"player_id": 2, "action": "raise", "amount": 100},
    ...
  ],
  "legal_actions": [
    {"type": "fold"},
    {"type": "call"},
    {"type": "raise", "min": 200, "max": 1450}
  ]
}

── Outbound (to game engine) ───────────────────────────────────────
{
  "action": "raise",
  "amount": 300
}
"""

import json
import re

VALID_ACTIONS = {"fold", "check", "call", "raise", "all_in"}

POSITION_LABELS = {
    "SB": "Small Blind",
    "BB": "Big Blind",
    "UTG": "Under the Gun",
    "MP": "Middle Position",
    "CO": "Cutoff",
    "BTN": "Button (Dealer)",
}

ROUND_LABELS = {
    "preflop": "Pre-Flop",
    "flop": "Flop",
    "turn": "Turn",
    "river": "River",
}


def build_user_message(game_state: dict) -> str:
    """
    Convert a game engine state dict into a concise natural-language
    user message for the LLM. Designed to be token-efficient while
    giving the agent everything it needs to decide.
    """
    lines = []

    round_label = ROUND_LABELS.get(game_state.get("round", ""), game_state.get("round", "unknown"))
    lines.append(f"=== {round_label} ===")

    hand_id = game_state.get("hand_id", "?")
    lines.append(f"Hand: {hand_id}")

    hole = game_state.get("hole_cards", [])
    lines.append(f"Your cards: {' '.join(hole)}")

    community = game_state.get("community_cards", [])
    if community:
        lines.append(f"Board: {' '.join(community)}")
    else:
        lines.append("Board: (none yet)")

    pos_raw = game_state.get("position", "?")
    pos_label = POSITION_LABELS.get(pos_raw, pos_raw)
    lines.append(f"Position: {pos_label}")

    pot = game_state.get("pot", 0)
    current_bet = game_state.get("current_bet", 0)
    stack = game_state.get("player_stack", 0)
    lines.append(f"Pot: {pot}  |  Current bet: {current_bet}  |  Your stack: {stack}")

    opponents = game_state.get("opponent_stacks", [])
    if opponents:
        opp_parts = [f"Player {o['id']}: {o['stack']}" for o in opponents]
        lines.append(f"Opponent stacks: {', '.join(opp_parts)}")

    # Full hand history (all streets up to now)
    full_history = game_state.get("hand_action_history", [])
    if full_history:
        lines.append("Hand action history:")
        current_phase = None
        for entry in full_history:
            phase = entry.get("phase", "")
            if phase != current_phase:
                current_phase = phase
                phase_label = ROUND_LABELS.get(phase, phase)
                lines.append(f"  [{phase_label}]")
            act = entry.get("action", "?")
            amt = entry.get("amount")
            pid = entry.get("player_id", "?")
            amt_str = f" {amt}" if amt is not None else ""
            lines.append(f"    Player {pid}: {act}{amt_str}")

    # Current street betting (for quick reference)
    history = game_state.get("betting_history", [])
    if history and full_history:
        lines.append(f"This street ({round_label}):")
        for entry in history:
            act = entry.get("action", "?")
            amt = entry.get("amount")
            pid = entry.get("player_id", "?")
            amt_str = f" {amt}" if amt is not None else ""
            lines.append(f"  Player {pid}: {act}{amt_str}")
    elif history:
        lines.append("Betting this round:")
        for entry in history:
            act = entry.get("action", "?")
            amt = entry.get("amount")
            pid = entry.get("player_id", "?")
            amt_str = f" {amt}" if amt is not None else ""
            lines.append(f"  Player {pid}: {act}{amt_str}")

    legal = game_state.get("legal_actions", [])
    if legal:
        action_strs = []
        for la in legal:
            atype = la["type"]
            if atype == "raise":
                action_strs.append(f"raise (min {la.get('min', '?')}, max {la.get('max', '?')})")
            else:
                action_strs.append(atype)
        lines.append(f"Legal actions: {' | '.join(action_strs)}")

    lines.append("")
    lines.append(
        "Decide your action now. Respond with ONLY a JSON object: "
        '{"action": "<action>", "amount": <number or null>, '
        '"reasoning": "<brief>", "table_talk": "<short punny one-liner>"}'
    )

    return "\n".join(lines)


def build_inference_request(assembled_prompt: dict, game_state: dict) -> dict:
    """
    Combine the agent's assembled config (from orchestrator.assemble_prompt)
    with a game state to produce the complete inference request payload.

    This is what gets sent to the inference layer (Modal / API).
    """
    user_message = build_user_message(game_state)

    request = {
        "agent_id": assembled_prompt["agent_id"],
        "agent_name": assembled_prompt["agent_name"],
        "model": assembled_prompt.get("resolved_model", assembled_prompt.get("model", "")),
        "model_type": assembled_prompt["model_type"],
        "temperature": assembled_prompt["temperature"],
        "messages": [
            {"role": "system", "content": assembled_prompt["assembled_system_prompt"]},
            {"role": "user", "content": user_message},
        ],
        "hand_id": game_state.get("hand_id"),
        "player_id": game_state.get("player_id"),
    }

    if "modal_config" in assembled_prompt:
        request["modal_config"] = assembled_prompt["modal_config"]
    if "api_config" in assembled_prompt:
        request["api_config"] = assembled_prompt["api_config"]

    return request


# ── Response Parsing ────────────────────────────────────────────────────────

_JSON_PATTERN = re.compile(r'\{[^{}]*\}')

DEFAULT_FALLBACK = {"action": "fold", "amount": None, "reasoning": "Fallback: invalid or missing response."}


def parse_action(raw_response: str, legal_actions: list[dict]) -> dict:
    """
    Parse the LLM's raw text response into a validated action dict.

    Tries to extract JSON from the response, validates the action is
    legal, clamps raise amounts, and falls back to fold on any failure.

    Returns: {"action": str, "amount": int|None, "reasoning": str, "parse_ok": bool}
    """
    legal_types = {la["type"] for la in legal_actions}

    extracted = _extract_json(raw_response)
    if not extracted:
        return {**DEFAULT_FALLBACK, "parse_ok": False, "raw": raw_response}

    action = str(extracted.get("action", "")).lower().strip()
    amount = extracted.get("amount")
    reasoning = str(extracted.get("reasoning", ""))
    table_talk = str(extracted.get("table_talk", "")).strip() or None

    if action == "all_in" and "all_in" not in legal_types:
        raise_action = _find_raise_action(legal_actions)
        if raise_action:
            action = "raise"
            amount = raise_action.get("max")

    if action not in legal_types:
        best = _best_fallback(legal_types)
        return {"action": best, "amount": None, "reasoning": f"Illegal action '{action}', falling back to {best}.", "parse_ok": False, "raw": raw_response, "table_talk": table_talk}

    if action == "raise":
        raise_spec = _find_raise_action(legal_actions)
        if raise_spec and amount is not None:
            try:
                amount = int(amount)
            except (ValueError, TypeError):
                amount = raise_spec.get("min")
            amount = max(raise_spec.get("min", 0), min(amount, raise_spec.get("max", amount)))
        elif raise_spec:
            amount = raise_spec.get("min")
    else:
        amount = None

    return {"action": action, "amount": amount, "reasoning": reasoning, "parse_ok": True, "table_talk": table_talk}


def _extract_json(text: str) -> dict | None:
    """Try to pull a JSON object out of the LLM response."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try finding JSON in markdown code blocks or inline
    matches = _JSON_PATTERN.findall(text)
    for candidate in matches:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _find_raise_action(legal_actions: list[dict]) -> dict | None:
    for la in legal_actions:
        if la["type"] == "raise":
            return la
    return None


def _best_fallback(legal_types: set[str]) -> str:
    """Pick the least aggressive legal action as fallback."""
    for preferred in ("check", "call", "fold"):
        if preferred in legal_types:
            return preferred
    return next(iter(legal_types)) if legal_types else "fold"
