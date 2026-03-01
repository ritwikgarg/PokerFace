from __future__ import annotations

from app.config import HISTORY_LEVELS, PLAY_STYLES, VALID_FRONTEND_MODEL_KEYS


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(", ".join(errors))


def validate_agent_config(data: dict) -> list[str]:
    """Validate incoming agent configuration (frontend camelCase fields).

    Field contract (matches frontend Zod schema):
        name             : str, 2-30 chars, required
        riskTolerance    : int, 0-100
        deception        : int, 0-100
        personalityPrompt: str, max 500 chars
        baseLLM          : one of the VALID_FRONTEND_MODEL_KEYS
        playStyle        : one of the PLAY_STYLES keys
        previousGamesHistory: int, 0-3
    """
    errors: list[str] = []

    # ── name ────────────────────────────────────────────────────────────────
    name = data.get("name")
    if not name or not isinstance(name, str):
        errors.append("'name' is required and must be a non-empty string.")
    elif len(name) < 2:
        errors.append("Agent name must be at least 2 characters.")
    elif len(name) > 30:
        errors.append("Agent name must be at most 30 characters.")

    # ── baseLLM ─────────────────────────────────────────────────────────────
    base_llm = data.get("baseLLM")
    if base_llm is not None:
        if base_llm not in VALID_FRONTEND_MODEL_KEYS:
            valid = ", ".join(sorted(VALID_FRONTEND_MODEL_KEYS))
            errors.append(f"Unknown baseLLM '{base_llm}'. Available: {valid}")

    # ── riskTolerance ───────────────────────────────────────────────────────
    risk = data.get("riskTolerance")
    if risk is not None:
        if not isinstance(risk, (int, float)):
            errors.append("'riskTolerance' must be a number.")
        elif not 0 <= risk <= 100:
            errors.append("'riskTolerance' must be between 0 and 100.")

    # ── deception ───────────────────────────────────────────────────────────
    deception = data.get("deception")
    if deception is not None:
        if not isinstance(deception, (int, float)):
            errors.append("'deception' must be a number.")
        elif not 0 <= deception <= 100:
            errors.append("'deception' must be between 0 and 100.")

    # ── personalityPrompt ───────────────────────────────────────────────────
    prompt = data.get("personalityPrompt")
    if prompt is not None:
        if not isinstance(prompt, str):
            errors.append("'personalityPrompt' must be a string.")
        elif len(prompt) > 500:
            errors.append("'personalityPrompt' must be under 500 characters.")

    # ── playStyle ───────────────────────────────────────────────────────────
    play_style = data.get("playStyle")
    if play_style is not None:
        if play_style not in PLAY_STYLES:
            valid = ", ".join(PLAY_STYLES.keys())
            errors.append(f"Unknown playStyle '{play_style}'. Available: {valid}")

    # ── previousGamesHistory ────────────────────────────────────────────────
    history = data.get("previousGamesHistory")
    if history is not None:
        if not isinstance(history, (int, float)):
            errors.append("'previousGamesHistory' must be a number.")
        elif int(history) not in HISTORY_LEVELS:
            valid = ", ".join(str(k) for k in sorted(HISTORY_LEVELS))
            errors.append(f"'previousGamesHistory' must be one of: {valid}")

    return errors
