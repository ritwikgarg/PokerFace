from __future__ import annotations

"""
PokerHand: full state machine for a single hand of No-Limit Texas Hold'em.

Lifecycle:
  init → post_blinds → deal_hole_cards → [PREFLOP betting] →
  deal_flop → [FLOP betting] → deal_turn → [TURN betting] →
  deal_river → [RIVER betting] → showdown → COMPLETE

The engine never trusts external input — every action is validated.
"""

import uuid
from enum import Enum

from app.engine.deck import Card, Deck
from app.engine.hand_evaluator import best_hand, hand_rank_name
from app.engine.action_validator import compute_legal_actions, validate_action


class HandPhase(Enum):
    INIT = "init"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    COMPLETE = "complete"


class PlayerState:
    __slots__ = (
        "player_id", "seat_index", "stack", "hole_cards",
        "bet_this_round", "total_bet", "is_folded", "is_all_in",
        "has_acted_this_round",
    )

    def __init__(self, player_id: str, seat_index: int, stack: int):
        self.player_id = player_id
        self.seat_index = seat_index
        self.stack = stack
        self.hole_cards: list[Card] = []
        self.bet_this_round = 0
        self.total_bet = 0
        self.is_folded = False
        self.is_all_in = False
        self.has_acted_this_round = False

    def place_bet(self, amount: int) -> int:
        """Place a bet, return actual amount posted (may be less if all-in)."""
        actual = min(amount, self.stack)
        self.stack -= actual
        self.bet_this_round += actual
        self.total_bet += actual
        if self.stack == 0:
            self.is_all_in = True
        return actual

    def reset_round(self):
        self.bet_this_round = 0
        self.has_acted_this_round = False

    def to_dict(self, reveal_cards: bool = False) -> dict:
        d = {
            "player_id": self.player_id,
            "seat_index": self.seat_index,
            "stack": self.stack,
            "bet_this_round": self.bet_this_round,
            "total_bet": self.total_bet,
            "is_folded": self.is_folded,
            "is_all_in": self.is_all_in,
        }
        if reveal_cards and self.hole_cards:
            d["hole_cards"] = [str(c) for c in self.hole_cards]
        return d


class PokerHand:
    """State machine for a single hand of No-Limit Hold'em."""

    def __init__(
        self,
        player_ids: list[str],
        stacks: list[int],
        dealer_index: int,
        small_blind: int,
        big_blind: int,
        seed: int | None = None,
    ):
        if len(player_ids) < 2:
            raise ValueError("Need at least 2 players")

        self.hand_id = str(uuid.uuid4())
        self.seed = seed
        self.deck = Deck(seed=seed)
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.dealer_index = dealer_index
        self.phase = HandPhase.INIT
        self.community_cards: list[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.min_raise_size = big_blind
        self.last_raiser_index: int | None = None
        self.action_index: int | None = None  # whose turn it is

        self.players: list[PlayerState] = []
        for i, (pid, stack) in enumerate(zip(player_ids, stacks)):
            self.players.append(PlayerState(pid, i, stack))

        self.action_log: list[dict] = []
        self.pots: list[dict] = []  # filled at showdown
        self.winners: list[dict] = []
        self._num_players = len(player_ids)

    # ── Public state queries ────────────────────────────────────────────────

    @property
    def current_player(self) -> PlayerState | None:
        if self.action_index is None:
            return None
        return self.players[self.action_index]

    @property
    def active_players(self) -> list[PlayerState]:
        return [p for p in self.players if not p.is_folded]

    @property
    def players_who_can_act(self) -> list[PlayerState]:
        return [p for p in self.players if not p.is_folded and not p.is_all_in]

    @property
    def is_hand_over(self) -> bool:
        return self.phase == HandPhase.COMPLETE

    # ── Phase progression ───────────────────────────────────────────────────

    def start(self) -> list[dict]:
        """Run the hand from INIT through dealing and return events."""
        events = []
        events += self._post_blinds()
        events += self._deal_hole_cards()
        self.phase = HandPhase.PREFLOP
        events += self._setup_betting_round()
        return events

    def apply_action(self, player_id: str, action: dict) -> list[dict]:
        """
        Apply a player's action. Returns a list of event dicts.
        Raises ValueError if the action is invalid.
        """
        if self.phase in (HandPhase.INIT, HandPhase.SHOWDOWN, HandPhase.COMPLETE):
            raise ValueError(f"Cannot act in phase {self.phase.value}")

        cp = self.current_player
        if cp is None or cp.player_id != player_id:
            raise ValueError(f"Not {player_id}'s turn")

        legal = self.get_legal_actions(player_id)
        is_valid, error = validate_action(action, legal)
        if not is_valid:
            raise ValueError(error)

        events = self._execute_action(cp, action)
        events += self._advance()
        return events

    def get_legal_actions(self, player_id: str) -> list[dict]:
        """Compute legal actions for a specific player."""
        p = self._get_player(player_id)
        if p.is_folded or p.is_all_in:
            return []
        can_check = (self.current_bet == p.bet_this_round)
        return compute_legal_actions(
            player_stack=p.stack,
            current_bet=self.current_bet,
            player_bet_this_round=p.bet_this_round,
            min_raise_size=self.min_raise_size,
            pot_size=self.pot,
            num_active_players=len(self.players_who_can_act),
            can_check=can_check,
        )

    # ── Internals ───────────────────────────────────────────────────────────

    def _get_player(self, player_id: str) -> PlayerState:
        for p in self.players:
            if p.player_id == player_id:
                return p
        raise ValueError(f"Player {player_id} not in hand")

    def _post_blinds(self) -> list[dict]:
        events = []
        n = self._num_players
        if n == 2:
            sb_i = self.dealer_index
            bb_i = (self.dealer_index + 1) % n
        else:
            sb_i = (self.dealer_index + 1) % n
            bb_i = (self.dealer_index + 2) % n

        sb_actual = self.players[sb_i].place_bet(self.small_blind)
        self.pot += sb_actual
        events.append({"event": "post_blind", "player_id": self.players[sb_i].player_id,
                        "blind": "SB", "amount": sb_actual})

        bb_actual = self.players[bb_i].place_bet(self.big_blind)
        self.pot += bb_actual
        self.current_bet = self.big_blind
        events.append({"event": "post_blind", "player_id": self.players[bb_i].player_id,
                        "blind": "BB", "amount": bb_actual})

        self.action_log.extend(events)
        return events

    def _deal_hole_cards(self) -> list[dict]:
        events = []
        for p in self.players:
            p.hole_cards = self.deck.deal(2)
            events.append({"event": "deal_hole", "player_id": p.player_id,
                            "cards": [str(c) for c in p.hole_cards]})
        self.action_log.extend(events)
        return events

    def _setup_betting_round(self) -> list[dict]:
        """Set up action order for the current betting round."""
        for p in self.players:
            p.reset_round()
            # Preserve bets from blind posting in preflop
            if self.phase == HandPhase.PREFLOP:
                p.has_acted_this_round = False

        if self.phase == HandPhase.PREFLOP:
            n = self._num_players
            if n == 2:
                first = self.dealer_index  # SB acts first preflop in HU
            else:
                first = (self.dealer_index + 3) % n  # UTG
            # Re-set bet_this_round from blind amounts already posted
            # (they were tracked in place_bet, we need them for this round)
        else:
            first = (self.dealer_index + 1) % self._num_players

        self.action_index = self._find_next_actor(first, include_start=True)
        self.last_raiser_index = None

        if self.action_index is None:
            return self._advance_phase()
        return [{"event": "turn", "player_id": self.players[self.action_index].player_id,
                 "phase": self.phase.value}]

    def _execute_action(self, player: PlayerState, action: dict) -> list[dict]:
        atype = action.get("type", "").lower()
        amount = action.get("amount")
        event = {"event": "action", "player_id": player.player_id,
                 "phase": self.phase.value, "action_type": atype}

        if atype == "fold":
            player.is_folded = True
        elif atype == "check":
            pass
        elif atype == "call":
            to_call = self.current_bet - player.bet_this_round
            actual = player.place_bet(to_call)
            self.pot += actual
            event["amount"] = actual
        elif atype in ("raise", "all_in"):
            target_total = int(amount) if amount else player.stack + player.bet_this_round
            raise_amount = target_total - player.bet_this_round
            actual = player.place_bet(raise_amount)
            self.pot += actual
            new_raise_size = (player.bet_this_round) - self.current_bet
            if new_raise_size > self.min_raise_size:
                self.min_raise_size = new_raise_size
            self.current_bet = player.bet_this_round
            self.last_raiser_index = player.seat_index
            event["amount"] = player.bet_this_round
            # Everyone else needs to act again
            for p in self.players:
                if p != player and not p.is_folded and not p.is_all_in:
                    p.has_acted_this_round = False

        player.has_acted_this_round = True
        self.action_log.append(event)
        return [event]

    def _advance(self) -> list[dict]:
        """After an action, find next actor or advance phase."""
        if len(self.active_players) == 1:
            return self._award_pot_single_winner()

        if self._is_betting_round_complete():
            return self._advance_phase()

        next_idx = self._find_next_actor(
            (self.action_index + 1) % self._num_players, include_start=True
        )
        if next_idx is None:
            return self._advance_phase()

        self.action_index = next_idx
        return [{"event": "turn", "player_id": self.players[next_idx].player_id,
                 "phase": self.phase.value}]

    def _is_betting_round_complete(self) -> bool:
        for p in self.players_who_can_act:
            if not p.has_acted_this_round:
                return False
            if p.bet_this_round != self.current_bet:
                return False
        return True

    def _find_next_actor(self, start: int, include_start: bool) -> int | None:
        n = self._num_players
        for offset in range(n):
            i = (start + offset) % n
            if offset == 0 and not include_start:
                continue
            p = self.players[i]
            if not p.is_folded and not p.is_all_in and not p.has_acted_this_round:
                return i
        return None

    def _advance_phase(self) -> list[dict]:
        events = []
        self.current_bet = 0
        self.min_raise_size = self.big_blind
        for p in self.players:
            p.bet_this_round = 0

        all_but_one_allin_or_folded = len(self.players_who_can_act) <= 1

        if self.phase == HandPhase.PREFLOP:
            self.phase = HandPhase.FLOP
            cards = self.deck.burn_and_deal(3)
            self.community_cards.extend(cards)
            events.append({"event": "deal_community", "phase": "flop",
                            "cards": [str(c) for c in cards]})
        elif self.phase == HandPhase.FLOP:
            self.phase = HandPhase.TURN
            cards = self.deck.burn_and_deal(1)
            self.community_cards.extend(cards)
            events.append({"event": "deal_community", "phase": "turn",
                            "cards": [str(c) for c in cards]})
        elif self.phase == HandPhase.TURN:
            self.phase = HandPhase.RIVER
            cards = self.deck.burn_and_deal(1)
            self.community_cards.extend(cards)
            events.append({"event": "deal_community", "phase": "river",
                            "cards": [str(c) for c in cards]})
        elif self.phase == HandPhase.RIVER:
            return events + self._showdown()
        else:
            return events + self._showdown()

        if all_but_one_allin_or_folded:
            return events + self._advance_phase()

        events += self._setup_betting_round()
        return events

    def _showdown(self) -> list[dict]:
        self.phase = HandPhase.SHOWDOWN
        events = []
        active = self.active_players

        # Evaluate hands
        evaluations = {}
        for p in active:
            all_cards = p.hole_cards + self.community_cards
            if len(all_cards) >= 5:
                evaluations[p.player_id] = best_hand(all_cards)
            else:
                evaluations[p.player_id] = (0,)  # shouldn't happen

        # Calculate pots (main + side pots)
        pot_segments = self._calculate_pots()
        self.pots = pot_segments

        # Award each pot
        for pot_info in pot_segments:
            eligible_ids = [pid for pid in pot_info["eligible"] if pid in evaluations]
            if not eligible_ids:
                continue
            best_eval = max(evaluations[pid] for pid in eligible_ids)
            pot_winners = [pid for pid in eligible_ids if evaluations[pid] == best_eval]
            share = pot_info["amount"] // len(pot_winners)
            remainder = pot_info["amount"] % len(pot_winners)

            for i, pid in enumerate(pot_winners):
                award = share + (1 if i < remainder else 0)
                player = self._get_player(pid)
                player.stack += award
                self.winners.append({
                    "player_id": pid,
                    "amount": award,
                    "hand_rank": hand_rank_name(evaluations[pid]),
                    "cards": [str(c) for c in player.hole_cards],
                })
                events.append({
                    "event": "award_pot",
                    "player_id": pid,
                    "amount": award,
                    "hand_rank": hand_rank_name(evaluations[pid]),
                })

        self.action_log.extend(events)
        self.phase = HandPhase.COMPLETE
        events.append({"event": "hand_complete", "hand_id": self.hand_id})
        return events

    def _award_pot_single_winner(self) -> list[dict]:
        """Everyone else folded — award entire pot to last player standing."""
        winner = self.active_players[0]
        winner.stack += self.pot
        self.winners.append({
            "player_id": winner.player_id,
            "amount": self.pot,
            "hand_rank": "Uncontested",
            "cards": [str(c) for c in winner.hole_cards],
        })
        event = {"event": "award_pot", "player_id": winner.player_id,
                 "amount": self.pot, "hand_rank": "Uncontested"}
        self.action_log.append(event)
        self.phase = HandPhase.COMPLETE
        return [event, {"event": "hand_complete", "hand_id": self.hand_id}]

    def _calculate_pots(self) -> list[dict]:
        """
        Calculate main pot and side pots from player bets.
        Returns list of {"amount": int, "eligible": [player_id, ...]}.
        """
        bet_levels = sorted(set(
            p.total_bet for p in self.players if p.total_bet > 0
        ))

        pots = []
        prev_level = 0
        for level in bet_levels:
            contribution_per_player = level - prev_level
            contributors = [p for p in self.players if p.total_bet >= level]
            eligible = [p.player_id for p in contributors if not p.is_folded]
            total = contribution_per_player * len(contributors)
            if total > 0 and eligible:
                pots.append({"amount": total, "eligible": eligible})
            prev_level = level

        return pots if pots else [{"amount": self.pot, "eligible": [p.player_id for p in self.active_players]}]

    def to_dict(self) -> dict:
        return {
            "hand_id": self.hand_id,
            "seed": self.seed,
            "phase": self.phase.value,
            "community_cards": [str(c) for c in self.community_cards],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "players": [p.to_dict() for p in self.players],
            "action_index": self.action_index,
            "current_player_id": self.current_player.player_id if self.current_player else None,
            "winners": self.winners,
            "action_log": self.action_log,
        }
