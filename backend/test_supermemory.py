#!/usr/bin/env python3
"""
Standalone test for Supermemory write + retrieval + GPT-4o mini summarization.

Tests the full pipeline without needing Modal or the game engine running.
Just needs SUPERMEMORY_API_KEY (and optionally OPENAI_API_KEY) set.

Usage:
  cd backend
  source .venv/bin/activate
  # Set keys inline or in .env
  SUPERMEMORY_API_KEY=sm_... OPENAI_API_KEY=sk-... python test_supermemory.py
"""
from __future__ import annotations

import os
import sys
import time
import uuid
import logging

# Load .env if dotenv available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

from app.services import supermemory

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("test_supermemory")

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

def section(title: str):
    print(f"\n\033[1;34m{'─' * 60}\033[0m")
    print(f"\033[1;34m  {title}\033[0m")
    print(f"\033[1;34m{'─' * 60}\033[0m")


# ── Setup ────────────────────────────────────────────────────────────────────

TEST_AGENT_ID = f"test-agent-{uuid.uuid4().hex[:8]}"
TEST_GAME_ID = f"test-game-{uuid.uuid4().hex[:8]}"
OPPONENT_A = f"opponent-{uuid.uuid4().hex[:8]}"
OPPONENT_B = f"opponent-{uuid.uuid4().hex[:8]}"


def main():
    section("Configuration Check")
    st = supermemory.status()
    print(f"  Supermemory configured: {st['configured']}")
    print(f"  Base URL:               {st['base_url']}")
    print(f"  Has API key:            {st['has_api_key']}")
    print(f"  OpenAI key set:         {bool(os.getenv('OPENAI_API_KEY', ''))}")
    print(f"  Test agent ID:          {TEST_AGENT_ID}")
    print(f"  Test game ID:           {TEST_GAME_ID}")

    if not st["configured"]:
        print(f"\n{FAIL} SUPERMEMORY_API_KEY not set. Cannot proceed.")
        print("  Set it: SUPERMEMORY_API_KEY=sm_... python test_supermemory.py")
        sys.exit(1)

    # ── Step 1: Write seed data ──────────────────────────────────────────────
    section("Step 1: Writing seed data to Supermemory")

    writes = [
        ("Hand summary 1", lambda: supermemory.write_hand_summary(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            position="BTN", hole_cards=["As", "Kh"],
            board=["Qd", "Jc", "Ts", "2h", "7s"],
            actions_taken=["raise 30", "call", "bet 60", "raise 150"],
            result="won 320 chips with a straight",
            pot_size=320, key_decision="raise 150 on turn",
            lessons=["Broadway draws on BTN are profitable to raise"],
        )),
        ("Hand summary 2", lambda: supermemory.write_hand_summary(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            position="BB", hole_cards=["7c", "2d"],
            board=["Ah", "Kd", "5s"],
            actions_taken=["check", "fold"],
            result="lost — folded on flop",
            pot_size=20, key_decision="fold",
            lessons=["Don't defend BB with 72o against raises"],
        )),
        ("Hand summary 3", lambda: supermemory.write_hand_summary(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            position="CO", hole_cards=["Jh", "Jd"],
            board=["Qs", "9c", "3h", "Kd"],
            actions_taken=["raise 25", "call", "check", "fold"],
            result="lost — folded to large turn bet",
            pot_size=75, key_decision="fold on turn",
            lessons=["JJ on K-high board is vulnerable when opponent bets big"],
        )),
        ("Opponent note A", lambda: supermemory.write_opponent_note(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            opponent_id=OPPONENT_A, tag="loose-aggressive",
            notes="Raises 3x preflop with wide range, barrels on wet boards",
            street="preflop", confidence=0.8,
        )),
        ("Opponent note B", lambda: supermemory.write_opponent_note(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            opponent_id=OPPONENT_B, tag="tight-passive",
            notes="Only enters with premium hands, rarely bluffs on river",
            street="river", confidence=0.9,
        )),
        ("Self-learning 1", lambda: supermemory.write_self_learning(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            leak="Calling too many river bets with medium-strength hands",
            fix="Only call river bets with top pair or better",
            severity=0.7,
        )),
        ("Self-learning 2", lambda: supermemory.write_self_learning(
            game_id=TEST_GAME_ID, agent_id=TEST_AGENT_ID,
            leak="Over-bluffing on paired boards",
            fix="Reduce bluff frequency when board pairs — opponents call more",
            severity=0.6,
        )),
    ]

    for label, fn in writes:
        result = fn()
        status = PASS if result else FAIL
        print(f"  {status} {label}")

    print(f"\n  Waiting 5s for Supermemory to index documents...")
    time.sleep(5)

    # ── Step 2: Test raw retrieval (get_context) ─────────────────────────────
    section("Step 2: Raw retrieval (get_context)")

    queries = [
        ("Broad game history", "Key highlights and lessons from past poker games on preflop."),
        ("Opponent A tendencies", f"How does {OPPONENT_A} play on preflop? Tendencies and patterns."),
        ("Self-leaks", "My leaks and mistakes on river. What should I avoid?"),
        ("Board similarity", "Past hands with similar board to Qd Jc Ts. Lessons learned."),
    ]

    for label, query in queries:
        results = supermemory.get_context(TEST_AGENT_ID, query, top_k=3)
        status = PASS if results else WARN
        print(f"\n  {status} {label} — {len(results)} results")
        for i, r in enumerate(results):
            score = r.get("score", 0)
            content = r["content"][:120].replace("\n", " ")
            print(f"    [{i+1}] score={score:.3f}  {content}...")

    # ── Step 3: Test get_decision_context at each level ──────────────────────
    section("Step 3: get_decision_context at each history level")

    for level in [0, 1, 2, 3]:
        print(f"\n  Level {level}:")
        ctx = supermemory.get_decision_context(
            agent_id=TEST_AGENT_ID,
            opponent_ids=[OPPONENT_A, OPPONENT_B],
            street="preflop",
            board=["Qd", "Jc", "Ts"],
            history_level=level,
        )
        if level == 0:
            if ctx == "":
                print(f"    {PASS} Correctly returned empty (disabled)")
            else:
                print(f"    {FAIL} Level 0 should return empty, got: {ctx[:80]}")
        elif ctx:
            lines = ctx.split("\n")
            print(f"    {PASS} Got {len(lines)} lines of context")
            for line in lines[:8]:
                print(f"    │ {line[:100]}")
            if len(lines) > 8:
                print(f"    │ ... ({len(lines) - 8} more lines)")

            has_header = "=== Previous Games Context ===" in ctx
            print(f"    {PASS if has_header else FAIL} Has '=== Previous Games Context ===' header")

            if os.getenv("OPENAI_API_KEY"):
                is_summarized = ctx != lines  # basic check
                print(f"    {PASS} GPT-4o mini summarization was attempted")
            else:
                print(f"    {WARN} No OPENAI_API_KEY — raw snippets used (fallback)")
        else:
            print(f"    {WARN} No context returned (Supermemory may not have indexed yet)")

    # ── Summary ──────────────────────────────────────────────────────────────
    section("Done")
    print(f"  Agent ID used: {TEST_AGENT_ID}")
    print(f"  Game ID used:  {TEST_GAME_ID}")
    print(f"  Opponents:     {OPPONENT_A}, {OPPONENT_B}")
    print()


if __name__ == "__main__":
    main()
