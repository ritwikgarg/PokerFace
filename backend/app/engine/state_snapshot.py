from __future__ import annotations

"""
Builds safe state snapshots for each player. Public info is shared with all;
private info (hole cards, memory pointer) is only included for the recipient.
"""

from app.engine.poker_game import PokerHand
from app.engine.table import Table


def build_public_state(table: Table) -> dict:
    """State visible to all players and spectators."""
    hand = table.current_hand
    state = {
        "table_id": table.id,
        "status": table.status.value,
        "hand_number": table.hand_number,
        "small_blind": table.small_blind,
        "big_blind": table.big_blind,
        "dealer_index": table.dealer_index,
        "seats": [s.to_dict() for s in table.seats],
    }

    if hand:
        state["hand"] = {
            "hand_id": hand.hand_id,
            "phase": hand.phase.value,
            "community_cards": [str(c) for c in hand.community_cards],
            "pot": hand.pot,
            "current_bet": hand.current_bet,
            "current_player_id": hand.current_player.player_id if hand.current_player else None,
            "players": [
                {
                    "player_id": p.player_id,
                    "seat_index": p.seat_index,
                    "stack": p.stack,
                    "bet_this_round": p.bet_this_round,
                    "is_folded": p.is_folded,
                    "is_all_in": p.is_all_in,
                }
                for p in hand.players
            ],
        }
    else:
        state["hand"] = None

    return state


def build_player_view(table: Table, player_id: str) -> dict:
    """
    Full state for a specific player: includes their hole cards and
    legal actions if it's their turn. This is what gets sent to the
    orchestrator (for agents) or directly to a human client.
    """
    public = build_public_state(table)
    hand = table.current_hand

    private = {"player_id": player_id, "hole_cards": [], "legal_actions": [], "is_your_turn": False}

    if hand:
        for p in hand.players:
            if p.player_id == player_id:
                private["hole_cards"] = [str(c) for c in p.hole_cards]
                break

        if hand.current_player and hand.current_player.player_id == player_id:
            private["is_your_turn"] = True
            private["legal_actions"] = hand.get_legal_actions(player_id)

    public["private"] = private
    return public


def build_game_state_for_orchestrator(table: Table, player_id: str) -> dict:
    """
    Produce the game_state dict in the format expected by
    services/game_state.py build_user_message(). Bridges engine → orchestrator.
    """
    hand = table.current_hand
    if not hand:
        return {}

    player = None
    for p in hand.players:
        if p.player_id == player_id:
            player = p
            break
    if not player:
        return {}

    # Determine position label
    n = len(hand.players)
    seat_offset = (player.seat_index - hand.dealer_index) % n
    position_map = {0: "BTN"}
    if n == 2:
        position_map = {0: "SB", 1: "BB"}
    elif n <= 6:
        position_map = {0: "BTN", 1: "SB", 2: "BB"}
        if n > 3:
            position_map[3] = "UTG"
        if n > 4:
            position_map[4] = "MP"
        if n > 5:
            position_map[5] = "CO"
    position = position_map.get(seat_offset, f"Seat{player.seat_index}")

    opponents = [
        {"id": p.player_id, "stack": p.stack}
        for p in hand.players
        if p.player_id != player_id and not p.is_folded
    ]

    # Current street's betting (for the concise "Betting this round" section)
    current_street_history = [
        entry for entry in hand.action_log
        if entry.get("event") == "action" and entry.get("phase") == hand.phase.value
    ]
    formatted_current = [
        {
            "player_id": e["player_id"],
            "action": e["action_type"],
            "amount": e.get("amount"),
        }
        for e in current_street_history
    ]

    # Full hand action log (all streets) so the agent sees the complete picture
    all_actions = [
        entry for entry in hand.action_log
        if entry.get("event") == "action"
    ]
    formatted_all = [
        {
            "player_id": e["player_id"],
            "action": e["action_type"],
            "amount": e.get("amount"),
            "phase": e.get("phase"),
        }
        for e in all_actions
    ]

    return {
        "hand_id": hand.hand_id,
        "round": hand.phase.value,
        "player_id": player.player_id,
        "hole_cards": [str(c) for c in player.hole_cards],
        "community_cards": [str(c) for c in hand.community_cards],
        "pot": hand.pot,
        "current_bet": hand.current_bet,
        "player_stack": player.stack,
        "opponent_stacks": opponents,
        "position": position,
        "betting_history": formatted_current,
        "hand_action_history": formatted_all,
        "legal_actions": hand.get_legal_actions(player_id),
    }
