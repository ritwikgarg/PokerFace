from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.config import (
    DEFAULTS,
    FRONTEND_MODEL_MAP,
    HISTORY_LEVELS,
    PLAY_STYLES,
    SUPPORTED_MODELS,
    VALID_FRONTEND_MODEL_KEYS,
    resolve_frontend_model,
)


class AgentConfig:
    """Represents a fully-configured LLM poker agent.

    Accepts the frontend field names (camelCase) and stores them as-is so that
    ``to_dict()`` returns a shape that the Next.js frontend can consume directly.
    Internally exposes derived properties (risk_score 0-1, resolved model key)
    for use by the orchestrator / prompt assembly layer.
    """

    def __init__(
        self,
        name: str,
        *,
        base_llm: str = DEFAULTS["baseLLM"],
        risk_tolerance: int = DEFAULTS["riskTolerance"],
        deception: int = DEFAULTS["deception"],
        personality_prompt: str = DEFAULTS["personalityPrompt"],
        play_style: str = DEFAULTS["playStyle"],
        previous_games_history: int = DEFAULTS["previousGamesHistory"],
        temperature: float = DEFAULTS["temperature"],
        user_id: str = "",
        agent_id: str | None = None,
    ):
        self.id = agent_id or str(uuid.uuid4())
        self.user_id = user_id
        self.name = name
        self.base_llm = base_llm
        self.risk_tolerance = risk_tolerance
        self.deception = deception
        self.personality_prompt = personality_prompt
        self.play_style = play_style
        self.previous_games_history = previous_games_history
        self.temperature = temperature
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    # ── Derived properties used by orchestrator ─────────────────────────────

    @property
    def risk_score(self) -> float:
        """0-1 float from the 0-100 frontend slider."""
        return self.risk_tolerance / 100.0

    @property
    def bluff_frequency(self) -> float:
        """0-1 float from the 0-100 deception slider."""
        return self.deception / 100.0

    @property
    def resolved_model(self) -> str:
        """Canonical backend model key resolved from the frontend alias."""
        return resolve_frontend_model(self.base_llm)

    @property
    def play_style_data(self) -> dict | None:
        return PLAY_STYLES.get(self.play_style)

    # ── Mutation ────────────────────────────────────────────────────────────

    _UPDATABLE = {
        "name", "base_llm", "risk_tolerance", "deception",
        "personality_prompt", "play_style", "previous_games_history",
        "temperature", "user_id",
    }

    # Mapping from camelCase request keys → internal attribute names
    _CAMEL_MAP = {
        "baseLLM": "base_llm",
        "riskTolerance": "risk_tolerance",
        "deception": "deception",
        "personalityPrompt": "personality_prompt",
        "playStyle": "play_style",
        "previousGamesHistory": "previous_games_history",
        "userId": "user_id",
        "name": "name",
        "temperature": "temperature",
    }

    def update(self, **kwargs):
        for key, value in kwargs.items():
            attr = self._CAMEL_MAP.get(key, key)
            if attr in self._UPDATABLE and value is not None:
                setattr(self, attr, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    # ── Serialization (matches frontend AgentConfig interface) ──────────────

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "riskTolerance": self.risk_tolerance,
            "deception": self.deception,
            "personalityPrompt": self.personality_prompt,
            "baseLLM": self.base_llm,
            "playStyle": self.play_style,
            "previousGamesHistory": self.previous_games_history,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentConfig:
        """Create from either camelCase (frontend) or snake_case (internal) payload."""
        return cls(
            name=data.get("name", ""),
            base_llm=data.get("baseLLM", data.get("base_llm", DEFAULTS["baseLLM"])),
            risk_tolerance=data.get("riskTolerance", data.get("risk_tolerance", DEFAULTS["riskTolerance"])),
            deception=data.get("deception", DEFAULTS["deception"]),
            personality_prompt=data.get("personalityPrompt", data.get("personality_prompt", DEFAULTS["personalityPrompt"])),
            play_style=data.get("playStyle", data.get("play_style", DEFAULTS["playStyle"])),
            previous_games_history=data.get("previousGamesHistory", data.get("previous_games_history", DEFAULTS["previousGamesHistory"])),
            temperature=data.get("temperature", DEFAULTS["temperature"]),
            user_id=data.get("userId", data.get("user_id", "")),
            agent_id=data.get("id"),
        )
