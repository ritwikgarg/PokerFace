from __future__ import annotations

import random
import string
from datetime import datetime, timezone

from app.config import MAX_PLAYERS, ROOM_CODE_LENGTH


_ROOM_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code(existing_codes: set[str]) -> str:
    for _ in range(100):
        code = "".join(random.choices(_ROOM_CHARS, k=ROOM_CODE_LENGTH))
        if code not in existing_codes:
            return code
    raise RuntimeError("Unable to generate unique room code")


class RoomPlayer:
    """A player slot in a room lobby."""

    def __init__(
        self,
        user_id: str,
        user_name: str,
        agent_id: str,
        agent_name: str,
        *,
        user_image: str | None = None,
        is_host: bool = False,
    ):
        self.user_id = user_id
        self.user_name = user_name
        self.user_image = user_image
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.is_ready = False
        self.is_host = is_host

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "userName": self.user_name,
            "userImage": self.user_image,
            "agentId": self.agent_id,
            "agentName": self.agent_name,
            "isReady": self.is_ready,
            "isHost": self.is_host,
        }


class Room:
    """A lobby room that holds players before a game starts."""

    def __init__(self, created_by: str, max_players: int = MAX_PLAYERS, code: str | None = None):
        self.code = code or ""
        self.created_by = created_by
        self.players: list[RoomPlayer] = []
        self.status: str = "waiting"  # "waiting" | "in-progress" | "finished"
        self.max_players = max_players
        self.table_id: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()

    # ── Player management ───────────────────────────────────────────────────

    def add_player(self, player: RoomPlayer) -> str | None:
        """Add a player. Returns error string or None on success."""
        if self.status != "waiting":
            return "Room is not accepting players."
        if len(self.players) >= self.max_players:
            return "Room is full."
        for p in self.players:
            if p.user_id == player.user_id:
                return "You are already in this room."
        self.players.append(player)
        return None

    def remove_player(self, user_id: str) -> str | None:
        before = len(self.players)
        self.players = [p for p in self.players if p.user_id != user_id]
        if len(self.players) == before:
            return "Player not in room."
        return None

    def set_ready(self, user_id: str, ready: bool = True) -> str | None:
        for p in self.players:
            if p.user_id == user_id:
                p.is_ready = ready
                return None
        return "Player not in room."

    @property
    def all_ready(self) -> bool:
        return len(self.players) >= 2 and all(p.is_ready for p in self.players)

    # ── Serialization ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "createdBy": self.created_by,
            "players": [p.to_dict() for p in self.players],
            "status": self.status,
            "maxPlayers": self.max_players,
            "createdAt": self.created_at,
        }
