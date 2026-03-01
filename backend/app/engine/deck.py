from __future__ import annotations

import random
from dataclasses import dataclass

RANKS = list(range(2, 15))  # 2..14, where 14 = Ace
SUITS = ["h", "d", "c", "s"]

RANK_SYMBOLS = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8",
    9: "9", 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A",
}
SYMBOL_TO_RANK = {v: k for k, v in RANK_SYMBOLS.items()}


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: str

    def __str__(self) -> str:
        return f"{RANK_SYMBOLS[self.rank]}{self.suit}"

    def __repr__(self) -> str:
        return str(self)

    @classmethod
    def from_str(cls, s: str) -> Card:
        return cls(rank=SYMBOL_TO_RANK[s[0]], suit=s[1])


class Deck:
    """A standard 52-card deck with deterministic seeded shuffling."""

    def __init__(self, seed: int | None = None):
        self.seed = seed
        self._rng = random.Random(seed)
        self._cards: list[Card] = []
        self.reset()

    def reset(self):
        self._cards = [Card(r, s) for s in SUITS for r in RANKS]
        self._rng.shuffle(self._cards)

    def deal(self, n: int = 1) -> list[Card]:
        dealt = self._cards[:n]
        self._cards = self._cards[n:]
        return dealt

    def burn_and_deal(self, n: int = 1) -> list[Card]:
        """Burn one card, then deal n cards (standard poker dealing)."""
        self._cards = self._cards[1:]  # burn
        return self.deal(n)

    @property
    def remaining(self) -> int:
        return len(self._cards)
