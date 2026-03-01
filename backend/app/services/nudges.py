from __future__ import annotations

"""
Human nudge system.

Humans can send structured prompts to influence an agent's behavior during a game.
Nudges are appended to the agent's per-game memory and surfaced on the next turn.

Permissions:
  - "owner": only the agent's creator can nudge
  - "admin": server admins can nudge any agent
  - "spectator": any spectator can nudge (disabled by default)

Nudges do NOT bypass the action schema or engine constraints.
"""

from datetime import datetime, timezone

from app.services.memory import get_or_create

MAX_NUDGE_CHARS = 500
MAX_NUDGES_PER_GAME = 20


class NudgePermission:
    OWNER = "owner"
    ADMIN = "admin"
    SPECTATOR = "spectator"


_nudge_log: list[dict] = []


def send_nudge(
    agent_id: str,
    game_id: str,
    message: str,
    from_user: str,
    permission_level: str = NudgePermission.OWNER,
    agent_owner_id: str | None = None,
) -> dict | str:
    """
    Send a nudge to an agent. Returns the nudge record or an error string.
    """
    if len(message) > MAX_NUDGE_CHARS:
        return f"Nudge exceeds {MAX_NUDGE_CHARS} character limit."

    if permission_level == NudgePermission.OWNER:
        if agent_owner_id and from_user != agent_owner_id:
            return "Only the agent's owner can send nudges."
    elif permission_level == NudgePermission.SPECTATOR:
        pass  # anyone can nudge
    # ADMIN is always allowed

    game_nudges = [n for n in _nudge_log if n["agent_id"] == agent_id and n["game_id"] == game_id]
    if len(game_nudges) >= MAX_NUDGES_PER_GAME:
        return "Nudge limit reached for this game."

    memory = get_or_create(agent_id, game_id)
    nudge_record = memory.add_nudge(message, from_user)

    full_record = {
        "agent_id": agent_id,
        "game_id": game_id,
        "from_user": from_user,
        "permission_level": permission_level,
        **nudge_record,
    }
    _nudge_log.append(full_record)
    return full_record


def get_nudges(agent_id: str, game_id: str) -> list[dict]:
    return [n for n in _nudge_log if n["agent_id"] == agent_id and n["game_id"] == game_id]


def get_all_nudges(game_id: str) -> list[dict]:
    return [n for n in _nudge_log if n["game_id"] == game_id]
