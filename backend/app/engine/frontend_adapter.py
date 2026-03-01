from __future__ import annotations

"""
Adapts the backend engine state into the exact shapes the Next.js frontend expects.

Frontend interfaces (from types/index.ts):
  Card         → { suit, rank, faceUp }
  PlayerState  → { seatIndex, userId, agentName, chips, currentBet, holeCards, ... }
  GameState    → { roomCode, phase, communityCards, pot, currentBet, players, ... }
  HandResult   → { winnerUserId, winnerName, handRank, potWon, players[] }
  ActionLogEntry → { playerName, action, amount?, timestamp }
"""

from datetime import datetime, timezone

from app.engine.deck import Card, RANK_SYMBOLS
from app.engine.poker_game import PokerHand, HandPhase, PlayerState as EnginePlayer
from app.engine.table import Table

# ── Card conversion ─────────────────────────────────────────────────────────

_SUIT_MAP = {"h": "hearts", "d": "diamonds", "c": "clubs", "s": "spades"}
_RANK_MAP = {v: v for v in ("2", "3", "4", "5", "6", "7", "8", "9")}
_RANK_MAP["T"] = "10"
_RANK_MAP["J"] = "J"
_RANK_MAP["Q"] = "Q"
_RANK_MAP["K"] = "K"
_RANK_MAP["A"] = "A"


def card_to_frontend(card: Card | str, *, face_up: bool = True) -> dict:
    """Convert a backend Card object or 'Ah' string to frontend shape."""
    if isinstance(card, str):
        rank_sym = card[0]
        suit_sym = card[1]
    else:
        rank_sym = RANK_SYMBOLS[card.rank]
        suit_sym = card.suit

    return {
        "suit": _SUIT_MAP.get(suit_sym, suit_sym),
        "rank": _RANK_MAP.get(rank_sym, rank_sym),
        "faceUp": face_up,
    }


def cards_to_frontend(cards: list, *, face_up: bool = True) -> list[dict]:
    return [card_to_frontend(c, face_up=face_up) for c in cards]


# ── Phase mapping ───────────────────────────────────────────────────────────

_PHASE_MAP = {
    "init": "pre-flop",
    "preflop": "pre-flop",
    "flop": "flop",
    "turn": "turn",
    "river": "river",
    "showdown": "showdown",
    "complete": "showdown",
}


def phase_to_frontend(phase: str | HandPhase) -> str:
    val = phase.value if isinstance(phase, HandPhase) else phase
    return _PHASE_MAP.get(val, val)


# ── Action mapping ──────────────────────────────────────────────────────────

_ACTION_MAP = {
    "fold": "fold",
    "check": "check",
    "call": "call",
    "raise": "raise",
    "all_in": "all-in",
    "post_blind": "post blind",
}


def action_to_frontend(action_type: str) -> str:
    return _ACTION_MAP.get(action_type, action_type)


# ── Player state ────────────────────────────────────────────────────────────

def player_to_frontend(
    p: EnginePlayer,
    hand: PokerHand,
    seat_index: int,
    *,
    agent_name: str = "",
    user_id: str = "",
    user_image: str | None = None,
    reveal_cards: bool = False,
) -> dict:
    """Build a frontend PlayerState dict from engine data."""
    n = hand._num_players
    sb_i = hand.dealer_index if n == 2 else (hand.dealer_index + 1) % n
    bb_i = (hand.dealer_index + 1) % n if n == 2 else (hand.dealer_index + 2) % n

    hole_cards = None
    if reveal_cards and p.hole_cards:
        hole_cards = [card_to_frontend(c) for c in p.hole_cards]

    is_active = (
        hand.current_player is not None
        and hand.current_player.player_id == p.player_id
    )

    last_action = None
    for entry in reversed(hand.action_log):
        if entry.get("player_id") == p.player_id and entry.get("event") == "action":
            last_action = action_to_frontend(entry.get("action_type", ""))
            break

    return {
        "seatIndex": seat_index,
        "userId": user_id or p.player_id,
        "agentName": agent_name or p.player_id,
        "userImage": user_image,
        "chips": p.stack,
        "currentBet": p.bet_this_round,
        "holeCards": hole_cards,
        "isFolded": p.is_folded,
        "isAllIn": p.is_all_in,
        "isDealer": p.seat_index == hand.dealer_index,
        "isSmallBlind": p.seat_index == sb_i,
        "isBigBlind": p.seat_index == bb_i,
        "isActive": is_active,
        "lastAction": last_action,
    }


# ── Action log ──────────────────────────────────────────────────────────────

def build_action_log(hand: PokerHand, name_map: dict[str, str] | None = None) -> list[dict]:
    """Convert engine action_log to frontend ActionLogEntry[]."""
    name_map = name_map or {}
    entries = []
    for e in hand.action_log:
        if e.get("event") not in ("action", "post_blind"):
            continue
        entries.append({
            "playerName": name_map.get(e.get("player_id", ""), e.get("player_id", "")),
            "action": action_to_frontend(e.get("action_type", e.get("blind", ""))),
            "amount": e.get("amount"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return entries


# ── Full game state ─────────────────────────────────────────────────────────

def build_frontend_game_state(
    table: Table,
    room_code: str,
    *,
    name_map: dict[str, str] | None = None,
    viewer_id: str | None = None,
) -> dict:
    """Build the full frontend GameState object from a Table.

    Args:
        name_map: player_id → agent display name
        viewer_id: if set, this player's hole cards are revealed
    """
    name_map = name_map or {}
    hand = table.current_hand
    if not hand:
        return {
            "roomCode": room_code,
            "phase": "pre-flop",
            "communityCards": [],
            "pot": 0,
            "currentBet": 0,
            "players": [],
            "dealerIndex": table.dealer_index,
            "activePlayerIndex": -1,
            "handNumber": table.hand_number,
            "actionLog": [],
        }

    players = []
    for i, p in enumerate(hand.players):
        reveal = (viewer_id is not None and p.player_id == viewer_id)
        players.append(player_to_frontend(
            p, hand, i,
            agent_name=name_map.get(p.player_id, p.player_id),
            user_id=p.player_id,
            reveal_cards=reveal,
        ))

    active_idx = -1
    if hand.current_player:
        for i, p in enumerate(hand.players):
            if p.player_id == hand.current_player.player_id:
                active_idx = i
                break

    return {
        "roomCode": room_code,
        "phase": phase_to_frontend(hand.phase),
        "communityCards": cards_to_frontend(hand.community_cards),
        "pot": hand.pot,
        "currentBet": hand.current_bet,
        "players": players,
        "dealerIndex": hand.dealer_index,
        "activePlayerIndex": active_idx,
        "handNumber": table.hand_number,
        "actionLog": build_action_log(hand, name_map),
    }


# ── Hand result ─────────────────────────────────────────────────────────────

def build_hand_result(hand: PokerHand, name_map: dict[str, str] | None = None) -> dict:
    """Build frontend HandResult from a completed hand."""
    name_map = name_map or {}

    primary_winner = hand.winners[0] if hand.winners else {}
    total_won = sum(w.get("amount", 0) for w in hand.winners)

    result_players = []
    for p in hand.players:
        winner_entry = next((w for w in hand.winners if w["player_id"] == p.player_id), None)
        chip_change = winner_entry["amount"] if winner_entry else -(p.total_bet)
        result_players.append({
            "userId": p.player_id,
            "agentName": name_map.get(p.player_id, p.player_id),
            "holeCards": [card_to_frontend(c) for c in p.hole_cards] if p.hole_cards else [],
            "handRank": winner_entry["hand_rank"] if winner_entry else "",
            "chipChange": chip_change,
        })

    return {
        "winnerUserId": primary_winner.get("player_id", ""),
        "winnerName": name_map.get(primary_winner.get("player_id", ""), ""),
        "handRank": primary_winner.get("hand_rank", ""),
        "potWon": total_won,
        "players": result_players,
    }
