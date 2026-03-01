from __future__ import annotations

"""
Table: manages seats, dealer rotation, and multi-hand match progression.
Owns the PokerHand lifecycle and links to the match-level metadata.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from app.engine.poker_game import PokerHand


class TableStatus(Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"


class Seat:
    __slots__ = ("index", "player_id", "player_type", "stack", "is_sitting_out")

    def __init__(self, index: int):
        self.index = index
        self.player_id: str | None = None
        self.player_type: str | None = None  # "agent" or "human"
        self.stack: int = 0
        self.is_sitting_out: bool = False

    @property
    def is_occupied(self) -> bool:
        return self.player_id is not None

    def sit(self, player_id: str, player_type: str, stack: int):
        self.player_id = player_id
        self.player_type = player_type
        self.stack = stack
        self.is_sitting_out = False

    def leave(self):
        pid = self.player_id
        self.player_id = None
        self.player_type = None
        self.stack = 0
        self.is_sitting_out = False
        return pid

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "player_id": self.player_id,
            "player_type": self.player_type,
            "stack": self.stack,
            "is_sitting_out": self.is_sitting_out,
            "is_occupied": self.is_occupied,
        }


class Table:
    def __init__(
        self,
        max_seats: int = 6,
        small_blind: int = 5,
        big_blind: int = 10,
        starting_stack: int = 1000,
        table_id: str | None = None,
        match_id: str | None = None,
    ):
        self.id = table_id or str(uuid.uuid4())
        self.match_id = match_id
        self.max_seats = max_seats
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.starting_stack = starting_stack
        self.status = TableStatus.WAITING
        self.seats: list[Seat] = [Seat(i) for i in range(max_seats)]
        self.dealer_index = 0
        self.hand_number = 0
        self.current_hand: PokerHand | None = None
        self.hand_seed_base: int | None = None
        self.completed_hands: list[dict] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    # ── Seat management ─────────────────────────────────────────────────────

    @property
    def occupied_seats(self) -> list[Seat]:
        return [s for s in self.seats if s.is_occupied]

    @property
    def active_seats(self) -> list[Seat]:
        return [s for s in self.seats if s.is_occupied and not s.is_sitting_out]

    def join(self, player_id: str, player_type: str, seat_index: int | None = None,
             buy_in: int | None = None) -> Seat | str:
        for s in self.seats:
            if s.player_id == player_id:
                return "Player already seated."

        stack = buy_in if buy_in else self.starting_stack

        if seat_index is not None:
            if seat_index < 0 or seat_index >= self.max_seats:
                return "Invalid seat index."
            if self.seats[seat_index].is_occupied:
                return "Seat is taken."
            self.seats[seat_index].sit(player_id, player_type, stack)
            return self.seats[seat_index]

        for s in self.seats:
            if not s.is_occupied:
                s.sit(player_id, player_type, stack)
                return s
        return "Table is full."

    def leave(self, player_id: str) -> str | None:
        for s in self.seats:
            if s.player_id == player_id:
                s.leave()
                return None
        return "Player not at table."

    # ── Hand lifecycle ──────────────────────────────────────────────────────

    def can_start_hand(self) -> tuple[bool, str]:
        active = self.active_seats
        if len(active) < 2:
            return False, "Need at least 2 active players."
        if self.status == TableStatus.PAUSED:
            return False, "Table is paused."
        if self.status == TableStatus.FINISHED:
            return False, "Table is finished."
        if self.current_hand and not self.current_hand.is_hand_over:
            return False, "Current hand is still in progress."
        return True, ""

    def start_hand(self, seed: int | None = None) -> tuple[PokerHand, list[dict]] | str:
        can, reason = self.can_start_hand()
        if not can:
            return reason

        if self.status == TableStatus.WAITING:
            self.status = TableStatus.ACTIVE

        # Advance dealer to next active seat
        if self.hand_number > 0:
            self.dealer_index = self._next_active_seat(self.dealer_index)

        self.hand_number += 1
        actual_seed = seed if seed is not None else (
            (self.hand_seed_base or 0) + self.hand_number
        )

        active = self.active_seats
        player_ids = [s.player_id for s in active]
        stacks = [s.stack for s in active]

        # Map dealer_index from table seat to player list index
        dealer_seat = self.seats[self.dealer_index]
        if dealer_seat in active:
            dealer_player_index = active.index(dealer_seat)
        else:
            dealer_player_index = 0

        hand = PokerHand(
            player_ids=player_ids,
            stacks=stacks,
            dealer_index=dealer_player_index,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            seed=actual_seed,
        )
        self.current_hand = hand
        events = hand.start()
        return hand, events

    def finish_hand(self) -> dict | str:
        """Finalize the current hand and sync stacks back to seats."""
        if not self.current_hand or not self.current_hand.is_hand_over:
            return "No completed hand to finalize."

        hand = self.current_hand
        summary = {
            "hand_id": hand.hand_id,
            "hand_number": self.hand_number,
            "seed": hand.seed,
            "winners": hand.winners,
            "pot": hand.pot,
            "community_cards": [str(c) for c in hand.community_cards],
            "action_log": hand.action_log,
            "player_results": {},
        }

        for hp in hand.players:
            for seat in self.active_seats:
                if seat.player_id == hp.player_id:
                    original_stack = seat.stack
                    seat.stack = hp.stack
                    delta = hp.stack - original_stack
                    summary["player_results"][hp.player_id] = {
                        "final_stack": hp.stack,
                        "delta": delta,
                        "folded": hp.is_folded,
                    }
                    break

        # Eliminate busted players
        for seat in self.active_seats:
            if seat.stack <= 0:
                seat.is_sitting_out = True

        self.completed_hands.append(summary)
        self.current_hand = None

        if len(self.active_seats) < 2:
            self.status = TableStatus.FINISHED

        return summary

    def pause(self):
        self.status = TableStatus.PAUSED

    def resume(self):
        if self.status == TableStatus.PAUSED:
            self.status = TableStatus.ACTIVE

    def finish_table(self):
        self.status = TableStatus.FINISHED

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _next_active_seat(self, from_index: int) -> int:
        n = self.max_seats
        for offset in range(1, n + 1):
            i = (from_index + offset) % n
            if self.seats[i].is_occupied and not self.seats[i].is_sitting_out:
                return i
        return from_index

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "match_id": self.match_id,
            "status": self.status.value,
            "max_seats": self.max_seats,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "starting_stack": self.starting_stack,
            "dealer_index": self.dealer_index,
            "hand_number": self.hand_number,
            "seats": [s.to_dict() for s in self.seats],
            "current_hand": self.current_hand.to_dict() if self.current_hand else None,
            "created_at": self.created_at,
        }
