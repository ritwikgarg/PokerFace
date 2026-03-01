from __future__ import annotations

"""
Core orchestration service.

Manages agent configurations in memory and assembles final prompts
by merging personality prompt + play style + risk calibration +
deception/bluff guidance.

Models are not called here — this service only *prepares* the payload
that will be sent to Modal (open-source) or an API provider later.
"""

from app.config import SUPPORTED_MODELS, PLAY_STYLES
from app.models.agent_config import AgentConfig
from app.presets.prompts import get_template
from app.services.table_talk import TABLE_TALK_PROMPT

_agents: dict[str, AgentConfig] = {}


# ── CRUD ────────────────────────────────────────────────────────────────────

def create_agent(data: dict) -> AgentConfig:
    agent = AgentConfig.from_dict(data)
    _agents[agent.id] = agent
    return agent


def get_agent(agent_id: str) -> AgentConfig | None:
    return _agents.get(agent_id)


def list_agents(user_id: str | None = None) -> list[AgentConfig]:
    if user_id:
        return [a for a in _agents.values() if a.user_id == user_id]
    return list(_agents.values())


def update_agent(agent_id: str, data: dict) -> AgentConfig | None:
    agent = _agents.get(agent_id)
    if not agent:
        return None
    agent.update(**data)
    return agent


def delete_agent(agent_id: str) -> bool:
    return _agents.pop(agent_id, None) is not None


# ── Prompt Assembly ─────────────────────────────────────────────────────────

def _build_risk_clause(risk_score: float) -> str:
    """Translate the 0-1 risk score into natural-language betting guidance."""
    if risk_score <= 0.2:
        return (
            "You have an extremely low risk tolerance. Fold marginal hands, "
            "avoid large bets, and only commit chips with very strong holdings."
        )
    if risk_score <= 0.4:
        return (
            "You have a low risk tolerance. Prefer cautious play, bet small "
            "with medium-strength hands, and avoid overcommitting without the nuts."
        )
    if risk_score <= 0.6:
        return (
            "You have a moderate risk tolerance. Balance value bets with the "
            "occasional bluff. Size your bets proportionally to hand strength."
        )
    if risk_score <= 0.8:
        return (
            "You have a high risk tolerance. You are willing to make large bets, "
            "semi-bluff aggressively, and put opponents to tough decisions."
        )
    return (
        "You have an extremely high risk tolerance. Go for maximum pressure: "
        "overbets, frequent bluffs, and fearless all-in moves when the "
        "situation is even marginally in your favor."
    )


def _build_deception_clause(bluff_freq: float) -> str:
    """Translate bluff frequency (0-1) to prompt guidance."""
    if bluff_freq <= 0.15:
        return "You almost never bluff. Only bet when you have strong hands."
    if bluff_freq <= 0.35:
        return "You bluff occasionally but mostly play straightforward poker."
    if bluff_freq <= 0.55:
        return "You have a balanced bluffing range. Mix bluffs and value bets."
    if bluff_freq <= 0.75:
        return "You bluff frequently, often representing stronger hands than you hold."
    return "You are a prolific bluffer. Deception is your primary weapon."


def _build_history_clause(level: int) -> str:
    """Translate previousGamesHistory level (0-3) into prompt guidance."""
    if level <= 0:
        return "You have no memory of previous games. Treat every hand fresh."
    if level == 1:
        return "You remember brief highlights from past games. Use them lightly."
    if level == 2:
        return (
            "You recall key patterns and opponent tendencies from past games. "
            "Factor them into your decisions."
        )
    return (
        "You have comprehensive memory of previous games: opponent profiles, "
        "board patterns, and strategic learnings. Use all of it aggressively."
    )


def assemble_prompt(agent: AgentConfig) -> dict:
    """
    Build the final assembled prompt from personality prompt, play style,
    risk calibration, and deception guidance.
    Returns the full config payload ready for dispatch to Modal or an API provider.
    """
    sections: list[str] = []

    default_template = get_template("default")
    if default_template:
        sections.append(default_template["template"])

    if agent.personality_prompt:
        sections.append(f"Agent personality: {agent.personality_prompt}")

    style_data = agent.play_style_data
    if style_data:
        sections.append(style_data["prompt_injection"])

    sections.append(_build_risk_clause(agent.risk_score))
    sections.append(_build_deception_clause(agent.bluff_frequency))
    sections.append(_build_history_clause(agent.previous_games_history))
    sections.append(TABLE_TALK_PROMPT)

    assembled_prompt = "\n\n".join(sections)

    resolved = agent.resolved_model
    model_meta = SUPPORTED_MODELS.get(resolved, {})
    payload = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "frontend_model": agent.base_llm,
        "resolved_model": resolved,
        "model_type": model_meta.get("type", "unknown"),
        "temperature": agent.temperature,
        "risk_score": agent.risk_score,
        "play_style": agent.play_style,
        "assembled_system_prompt": assembled_prompt,
    }

    if model_meta.get("type") == "open_source":
        payload["modal_config"] = {
            "hf_repo_id": model_meta["hf_repo_id"],
            "recommended_gpu": model_meta["recommended_gpu"],
            "context_window": model_meta["context_window"],
        }
    elif model_meta.get("type") == "api":
        payload["api_config"] = {
            "provider": model_meta["provider"],
            "context_window": model_meta["context_window"],
        }

    return payload
