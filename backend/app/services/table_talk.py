from __future__ import annotations

"""
Table talk: automated trash talk / banter between agents.

Each turn, the LLM is prompted to include a short one-liner alongside
its action. This module filters it for content safety before broadcasting.
"""

import re

MAX_TALK_CHARS = 150

# Words/patterns that are never allowed, even in poker banter
_BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        # slurs, heavy profanity, identity-based attacks
        r"\bfuck\b", r"\bshit\b", r"\bass\b", r"\bbitch\b", r"\bdamn\b",
        r"\bslut\b", r"\bwhore\b", r"\bcunt\b", r"\bdick\b", r"\bpiss\b",
        r"\bretard", r"\bfag", r"\bnig",
        r"\bkill\s+(your|my|him|her|them)",
        r"\bdie\b", r"\bsuicid", r"\brape\b",
        # real-money / scam bait
        r"\bvenmo\b", r"\bpaypal\b", r"\bsend\s+money",
        r"\bhttp[s]?://",
        # prompt injection attempts
        r"ignore\s+(previous|above|all)\s+(instructions|prompts)",
        r"system\s*prompt",
        r"you\s+are\s+now\s+",
    ]
]

# Light substitutions allowed — poker flavor
_SOFT_REPLACEMENTS = {
    r"\bhell\b": "heck",
    r"\bcrap\b": "crud",
}

# Poker-themed fallback lines when the LLM generates something blocked
FALLBACK_LINES = [
    "Nice hand... said no one ever. 🃏",
    "I've seen better plays from a fish at a sushi bar. 🐟",
    "You call that a raise? My grandma bets harder at bingo.",
    "All-in on vibes, zero on strategy.",
    "Folding? That's the first smart thing you've done.",
    "I'm not bluffing. Okay maybe a little. 😏",
    "The only thing you're winning is my respect... just kidding.",
    "Read 'em and weep? More like read 'em and sleep. 😴",
    "My cards are trembling... with excitement.",
    "That bet was so small, the blinds didn't even notice.",
    "Is this poker or a charity event? 💸",
    "I'd say good luck, but you're going to need a miracle.",
    "Your poker face needs a firmware update.",
    "Raising the stakes and your blood pressure. 📈",
    "Call me butter, because I'm on a roll. 🧈",
]

_fallback_idx = 0


def filter_table_talk(raw: str, agent_name: str = "") -> str | None:
    """
    Sanitize LLM-generated table talk.
    Returns cleaned string, a fallback, or None if talk was empty.
    """
    if not raw or not raw.strip():
        return None

    talk = raw.strip()

    if len(talk) > MAX_TALK_CHARS:
        talk = talk[:MAX_TALK_CHARS].rsplit(" ", 1)[0] + "..."

    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(talk):
            return _get_fallback()

    for pattern_str, replacement in _SOFT_REPLACEMENTS.items():
        talk = re.sub(pattern_str, replacement, talk, flags=re.IGNORECASE)

    return talk


def _get_fallback() -> str:
    global _fallback_idx
    line = FALLBACK_LINES[_fallback_idx % len(FALLBACK_LINES)]
    _fallback_idx += 1
    return line


# ── Prompt injection for system prompt ───────────────────────────────────────

TABLE_TALK_PROMPT = (
    "IMPORTANT — Table Talk: Along with your action, include a short, punny, "
    "intimidating, or funny one-liner as table banter. Keep it under 120 "
    "characters, poker-themed, and PG-rated. Be creative, witty, and in "
    "character. Think poker trash talk meets stand-up comedy.\n"
    "Add it as a \"table_talk\" field in your JSON response.\n"
    "Examples:\n"
    '  - "I\'d fold too if I had your cards... oh wait, I can\'t see them. Yet."\n'
    '  - "Raising like my rent — aggressively and without mercy."\n'
    '  - "You call that a bet? My chip stack laughed."\n'
    '  - "All-in on confidence, baby."\n'
)
