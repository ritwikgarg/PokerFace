from __future__ import annotations

"""
Mediated inter-agent communication.

All messages pass through the orchestrator — never peer-to-peer.
Rules:
  - Messages can only be sent between hands or at designated phases.
  - Each message has a token/character limit.
  - Messages can be public (visible to table) or private (two-agent channel).
  - The engine and orchestrator enforce that no private game state leaks.
"""

from datetime import datetime, timezone

MAX_MESSAGE_CHARS = 280
MAX_MESSAGES_PER_HAND = 2
MAX_MESSAGES_PER_AGENT_PER_GAME = 50


class MessagePhase:
    BETWEEN_HANDS = "between_hands"
    ON_YOUR_TURN = "on_your_turn"
    ANY = "any"

ALLOWED_PHASES = {MessagePhase.BETWEEN_HANDS, MessagePhase.ON_YOUR_TURN, MessagePhase.ANY}


# ── In-memory message store per game ────────────────────────────────────────
_channels: dict[str, list[dict]] = {}  # keyed by game_id


def send_message(
    game_id: str,
    sender_id: str,
    content: str,
    phase: str,
    recipient_id: str | None = None,
    current_hand_number: int = 0,
    communication_enabled: bool = True,
) -> dict | str:
    """
    Send an inter-agent message. Returns the message dict or an error string.
    recipient_id=None means public message to the table.
    """
    if not communication_enabled:
        return "Inter-agent communication is disabled for this game."

    if len(content) > MAX_MESSAGE_CHARS:
        return f"Message exceeds {MAX_MESSAGE_CHARS} character limit ({len(content)} chars)."

    if phase not in ALLOWED_PHASES:
        return f"Invalid message phase '{phase}'. Allowed: {ALLOWED_PHASES}"

    messages = _channels.get(game_id, [])
    agent_messages_this_game = [m for m in messages if m["sender_id"] == sender_id]
    if len(agent_messages_this_game) >= MAX_MESSAGES_PER_AGENT_PER_GAME:
        return "Message limit reached for this game."

    agent_messages_this_hand = [
        m for m in agent_messages_this_game
        if m.get("hand_number") == current_hand_number
    ]
    if len(agent_messages_this_hand) >= MAX_MESSAGES_PER_HAND:
        return "Message limit reached for this hand."

    msg = {
        "id": f"{game_id}-{len(messages)}",
        "game_id": game_id,
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "content": content,
        "phase": phase,
        "is_public": recipient_id is None,
        "hand_number": current_hand_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if game_id not in _channels:
        _channels[game_id] = []
    _channels[game_id].append(msg)

    return msg


def get_messages_for_player(game_id: str, player_id: str) -> list[dict]:
    """Get all messages a specific player is allowed to see."""
    messages = _channels.get(game_id, [])
    return [
        m for m in messages
        if m["is_public"] or m["sender_id"] == player_id or m["recipient_id"] == player_id
    ]


def get_public_messages(game_id: str) -> list[dict]:
    messages = _channels.get(game_id, [])
    return [m for m in messages if m["is_public"]]


def get_all_messages(game_id: str) -> list[dict]:
    return _channels.get(game_id, [])


def clear_game_messages(game_id: str):
    _channels.pop(game_id, None)
