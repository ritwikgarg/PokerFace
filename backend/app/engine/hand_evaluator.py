from __future__ import annotations

from collections import Counter
from enum import IntEnum
from itertools import combinations

from app.engine.deck import Card


class HandRank(IntEnum):
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


def evaluate_hand(cards: list[Card]) -> tuple:
    """
    Evaluate exactly 5 cards. Returns a comparable tuple:
    (HandRank, *tiebreakers) — higher is better.
    """
    ranks = sorted([c.rank for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1

    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
            straight_high = unique_ranks[0]
        elif unique_ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5  # wheel (A-2-3-4-5), 5-high straight

    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    pattern = sorted(counts.values(), reverse=True)

    if is_straight and is_flush:
        return (HandRank.STRAIGHT_FLUSH, straight_high)
    if pattern == [4, 1]:
        return (HandRank.FOUR_OF_A_KIND, groups[0][0], groups[1][0])
    if pattern == [3, 2]:
        return (HandRank.FULL_HOUSE, groups[0][0], groups[1][0])
    if is_flush:
        return (HandRank.FLUSH, *ranks)
    if is_straight:
        return (HandRank.STRAIGHT, straight_high)
    if pattern == [3, 1, 1]:
        kickers = sorted([g[0] for g in groups if g[1] == 1], reverse=True)
        return (HandRank.THREE_OF_A_KIND, groups[0][0], *kickers)
    if pattern == [2, 2, 1]:
        pairs = sorted([g[0] for g in groups if g[1] == 2], reverse=True)
        kicker = [g[0] for g in groups if g[1] == 1][0]
        return (HandRank.TWO_PAIR, pairs[0], pairs[1], kicker)
    if pattern == [2, 1, 1, 1]:
        pair_rank = groups[0][0]
        kickers = sorted([g[0] for g in groups if g[1] == 1], reverse=True)
        return (HandRank.ONE_PAIR, pair_rank, *kickers)

    return (HandRank.HIGH_CARD, *ranks)


def best_hand(cards: list[Card]) -> tuple:
    """
    Given 5–7 cards, find the best possible 5-card poker hand.
    Returns the evaluation tuple for the best combination.
    """
    if len(cards) < 5:
        raise ValueError(f"Need at least 5 cards, got {len(cards)}")
    if len(cards) == 5:
        return evaluate_hand(cards)

    return max(evaluate_hand(list(combo)) for combo in combinations(cards, 5))


def hand_rank_name(evaluation: tuple) -> str:
    """Human-readable name for an evaluation tuple."""
    names = {
        HandRank.HIGH_CARD: "High Card",
        HandRank.ONE_PAIR: "One Pair",
        HandRank.TWO_PAIR: "Two Pair",
        HandRank.THREE_OF_A_KIND: "Three of a Kind",
        HandRank.STRAIGHT: "Straight",
        HandRank.FLUSH: "Flush",
        HandRank.FULL_HOUSE: "Full House",
        HandRank.FOUR_OF_A_KIND: "Four of a Kind",
        HandRank.STRAIGHT_FLUSH: "Straight Flush",
    }
    return names.get(evaluation[0], "Unknown")
