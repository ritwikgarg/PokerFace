from __future__ import annotations

"""
Computes legal actions for a player and validates submitted actions.
This is the single source of truth for what moves are allowed.
"""


def compute_legal_actions(
    player_stack: int,
    current_bet: int,
    player_bet_this_round: int,
    min_raise_size: int,
    pot_size: int,
    num_active_players: int,
    can_check: bool,
) -> list[dict]:
    """
    Returns the list of legal actions for a player.
    Each action is a dict with 'type' and optional 'min'/'max'.
    """
    to_call = current_bet - player_bet_this_round
    actions = []

    actions.append({"type": "fold"})

    if to_call == 0 and can_check:
        actions.append({"type": "check"})

    if to_call > 0:
        if to_call >= player_stack:
            actions.append({"type": "call", "amount": player_stack})
        else:
            actions.append({"type": "call", "amount": to_call})

    if num_active_players >= 2:
        if to_call >= player_stack:
            pass  # can only call all-in, can't raise
        else:
            min_raise_total = current_bet + min_raise_size
            remaining_after_call = player_stack - to_call
            if remaining_after_call > 0:
                raise_min = max(min_raise_size, 1)
                raise_max = player_stack - to_call if to_call < player_stack else 0
                if raise_max > 0:
                    raise_min = min(raise_min, raise_max)
                    actions.append({
                        "type": "raise",
                        "min": raise_min + current_bet,
                        "max": player_stack + player_bet_this_round,
                    })

    if player_stack > 0:
        has_raise = any(a["type"] == "raise" for a in actions)
        if not has_raise:
            actions.append({"type": "all_in", "amount": player_stack + player_bet_this_round})
        else:
            raise_action = next(a for a in actions if a["type"] == "raise")
            if raise_action["max"] == player_stack + player_bet_this_round:
                pass  # raise max already covers all-in

    return actions


def validate_action(
    action: dict,
    legal_actions: list[dict],
) -> tuple[bool, str]:
    """
    Validate a submitted action against the legal actions list.
    Returns (is_valid, error_message).
    """
    action_type = action.get("type", "").lower()
    amount = action.get("amount")

    legal_types = {a["type"] for a in legal_actions}

    if action_type not in legal_types:
        return False, f"Action '{action_type}' is not legal. Legal: {legal_types}"

    if action_type == "raise":
        raise_spec = next((a for a in legal_actions if a["type"] == "raise"), None)
        if raise_spec is None:
            return False, "Raise is not a legal action."
        if amount is None:
            return False, "Raise requires an 'amount'."
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return False, f"Raise amount must be an integer, got '{amount}'."
        if amount < raise_spec["min"]:
            return False, f"Raise amount {amount} is below minimum {raise_spec['min']}."
        if amount > raise_spec["max"]:
            return False, f"Raise amount {amount} exceeds maximum {raise_spec['max']}."

    if action_type == "all_in":
        allin_spec = next((a for a in legal_actions if a["type"] == "all_in"), None)
        if allin_spec is None:
            raise_spec = next((a for a in legal_actions if a["type"] == "raise"), None)
            if raise_spec:
                action["type"] = "raise"
                action["amount"] = raise_spec["max"]
            else:
                call_spec = next((a for a in legal_actions if a["type"] == "call"), None)
                if call_spec:
                    action["type"] = "call"
                    action["amount"] = call_spec.get("amount")

    return True, ""
