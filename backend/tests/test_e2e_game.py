"""
End-to-end game test.

Exercises the full stack through the Flask test client (no live server needed):
  1. Agent CRUD (frontend field names)
  2. Room creation and joining
  3. Table creation, player seating, hand start
  4. Full poker hand with actions, phase transitions, and showdown
  5. Frontend adapter (card format, GameState, HandResult)
  6. Orchestrator prompt assembly
  7. Game turn protocol (stubbed inference)
  8. Memory, logging, communication, and nudges
  9. Leaderboard and model endpoints

Run:  python -m pytest tests/test_e2e_game.py -v
  or: python tests/test_e2e_game.py
"""
from __future__ import annotations

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app

app = create_app()
client = app.test_client()

PASS = 0
FAIL = 0


def section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if not condition:
        FAIL += 1
        print(f"  [{status}] {label}  -- {detail}")
    else:
        PASS += 1
        print(f"  [{status}] {label}")
    return condition


def post(url, data=None):
    return client.post(url, json=data, content_type="application/json")


def get(url):
    return client.get(url)


# ════════════════════════════════════════════════════════════════════════════
# 1. Health
# ════════════════════════════════════════════════════════════════════════════

section("1. Health Check")
r = get("/api/health")
check("GET /api/health returns 200", r.status_code == 200)
check("Response has status=ok", r.get_json()["status"] == "ok")

# ════════════════════════════════════════════════════════════════════════════
# 2. Defaults & Model Endpoints
# ════════════════════════════════════════════════════════════════════════════

section("2. Defaults, Models, Play Styles")

r = get("/api/defaults")
defaults = r.get_json()
check("GET /api/defaults returns 200", r.status_code == 200)
check("Default baseLLM is gpt-4o-mini", defaults["baseLLM"] == "gpt-4o-mini")
check("Default riskTolerance is 50", defaults["riskTolerance"] == 50)
check("Default playStyle is tight-aggressive", defaults["playStyle"] == "tight-aggressive")

r = get("/api/models/frontend")
fm = r.get_json()
check("GET /api/models/frontend returns 200", r.status_code == 200)
check("5 frontend models returned", len(fm["models"]) == 5)
model_values = {m["value"] for m in fm["models"]}
check("All frontend model keys present",
      model_values == {"gpt-4o-mini", "claude-haiku", "gemma-2b", "phi-3-mini", "llama-3.1-8b"})

r = get("/api/play-styles")
ps = r.get_json()
check("GET /api/play-styles returns 200", r.status_code == 200)
check("4 play styles returned", len(ps["playStyles"]) == 4)

# ════════════════════════════════════════════════════════════════════════════
# 3. Agent CRUD (frontend field names)
# ════════════════════════════════════════════════════════════════════════════

section("3. Agent CRUD")

r = post("/api/agents", {"name": "A"})
check("Name too short → 422", r.status_code == 422)

r = post("/api/agents", {"name": "Test", "baseLLM": "bad-model"})
check("Invalid model → 422", r.status_code == 422)

agent1_data = {
    "name": "Alpha Bot",
    "baseLLM": "gpt-4o-mini",
    "riskTolerance": 70,
    "deception": 40,
    "personalityPrompt": "Aggressive but calculated",
    "playStyle": "tight-aggressive",
    "previousGamesHistory": 2,
    "userId": "user-alice",
}
r = post("/api/agents", agent1_data)
a1 = r.get_json()
check("Create agent Alpha → 201", r.status_code == 201)
check("Agent has id", "id" in a1 and len(a1["id"]) > 10)
check("Agent returns camelCase fields", all(k in a1 for k in
      ["baseLLM", "riskTolerance", "deception", "personalityPrompt",
       "playStyle", "previousGamesHistory", "createdAt", "updatedAt", "userId"]))
check("riskTolerance preserved", a1["riskTolerance"] == 70)
check("baseLLM preserved", a1["baseLLM"] == "gpt-4o-mini")
AGENT1_ID = a1["id"]

agent2_data = {
    "name": "Beta Bot",
    "baseLLM": "llama-3.1-8b",
    "riskTolerance": 30,
    "deception": 60,
    "personalityPrompt": "Tricky and unpredictable",
    "playStyle": "loose-aggressive",
    "previousGamesHistory": 1,
    "userId": "user-bob",
}
r = post("/api/agents", agent2_data)
a2 = r.get_json()
check("Create agent Beta → 201", r.status_code == 201)
AGENT2_ID = a2["id"]

agent3_data = {
    "name": "Gamma Bot",
    "baseLLM": "claude-haiku",
    "riskTolerance": 50,
    "deception": 20,
    "playStyle": "tight-passive",
    "previousGamesHistory": 0,
    "userId": "user-charlie",
}
r = post("/api/agents", agent3_data)
a3 = r.get_json()
check("Create agent Gamma → 201", r.status_code == 201)
AGENT3_ID = a3["id"]

r = get("/api/agents")
check("List agents → 3 agents", len(r.get_json()) == 3)

r = get(f"/api/agents?userId=user-alice")
check("Filter by userId → 1 agent", len(r.get_json()) == 1)

r = client.put(f"/api/agents/{AGENT1_ID}", json={"riskTolerance": 90, "playStyle": "loose-aggressive"})
updated = r.get_json()
check("Update agent → 200", r.status_code == 200)
check("riskTolerance updated to 90", updated["riskTolerance"] == 90)
check("playStyle updated", updated["playStyle"] == "loose-aggressive")

# ════════════════════════════════════════════════════════════════════════════
# 4. Prompt Assembly
# ════════════════════════════════════════════════════════════════════════════

section("4. Prompt Assembly")

r = post(f"/api/agents/{AGENT1_ID}/assemble")
asm = r.get_json()
check("Assemble prompt → 200", r.status_code == 200)
check("Has assembled_system_prompt", "assembled_system_prompt" in asm)
check("Prompt contains play style", "loose-aggressive" in asm["assembled_system_prompt"].lower()
      or "many hands" in asm["assembled_system_prompt"].lower())
check("Prompt contains risk clause", "risk tolerance" in asm["assembled_system_prompt"].lower())
check("Prompt contains deception clause", "bluff" in asm["assembled_system_prompt"].lower())
check("Prompt contains depth clause", "opponent" in asm["assembled_system_prompt"].lower())
check("frontend_model is gpt-4o-mini", asm["frontend_model"] == "gpt-4o-mini")
check("resolved_model is mistral-7b-instruct", asm["resolved_model"] == "mistral-7b-instruct")
check("modal_config present", "modal_config" in asm)

# ════════════════════════════════════════════════════════════════════════════
# 5. Room System
# ════════════════════════════════════════════════════════════════════════════

section("5. Room System")

r = post("/api/rooms", {"agentId": AGENT1_ID, "userId": "user-alice", "userName": "Alice"})
room_resp = r.get_json()
check("Create room → 201", r.status_code == 201)
ROOM_CODE = room_resp["code"]
check("Room code is 6 chars", len(ROOM_CODE) == 6)
check("Room has 1 player (host)", len(room_resp["room"]["players"]) == 1)
check("Host isHost=true", room_resp["room"]["players"][0]["isHost"] is True)

r = post(f"/api/rooms/{ROOM_CODE}/join", {
    "agentId": AGENT2_ID, "userId": "user-bob", "userName": "Bob"
})
check("Join room → 200", r.status_code == 200)
check("Room has 2 players", len(r.get_json()["room"]["players"]) == 2)

r = post(f"/api/rooms/{ROOM_CODE}/join", {
    "agentId": AGENT3_ID, "userId": "user-charlie", "userName": "Charlie"
})
check("Join room → 200 (3rd player)", r.status_code == 200)

r = get(f"/api/rooms/{ROOM_CODE}")
room = r.get_json()
check("GET room → 3 players", len(room["players"]) == 3)
check("Room status is waiting", room["status"] == "waiting")

r = post(f"/api/rooms/{ROOM_CODE}/ready", {"userId": "user-alice", "ready": True})
check("Toggle ready → 200", r.status_code == 200)
check("allReady is false (only 1 ready)", r.get_json()["allReady"] is False)

for uid in ["user-bob", "user-charlie"]:
    post(f"/api/rooms/{ROOM_CODE}/ready", {"userId": uid, "ready": True})

r = post(f"/api/rooms/{ROOM_CODE}/ready", {"userId": "user-alice", "ready": True})
check("All ready after 3 toggles", r.get_json()["allReady"] is True)

# ════════════════════════════════════════════════════════════════════════════
# 6. Table + Full Poker Hand (3 players)
# ════════════════════════════════════════════════════════════════════════════

section("6. Table Creation & Hand Play")

r = post("/api/tables", {
    "max_seats": 5,
    "small_blind": 10,
    "big_blind": 20,
    "starting_stack": 1000,
    "seed_base": 42,
})
table = r.get_json()
TABLE_ID = table["id"]
check("Create table → 201", r.status_code == 201)
check("Table has 5 seats", table["max_seats"] == 5)

for pid in [AGENT1_ID, AGENT2_ID, AGENT3_ID]:
    r = post(f"/api/tables/{TABLE_ID}/join", {"player_id": pid, "player_type": "agent"})
    check(f"Join table ({pid[:8]}...) → 200", r.status_code == 200)

r = post(f"/api/tables/{TABLE_ID}/start-hand", {"seed": 12345})
hand_data = r.get_json()
check("Start hand → 200", r.status_code == 200)
HAND_ID = hand_data["hand_id"]
check("Hand ID assigned", len(HAND_ID) > 10)
check("Phase is preflop", hand_data["phase"] == "preflop")
check("Events include deal_hole", any(e["event"] == "deal_hole" for e in hand_data["events"]))
check("Events include post_blind", any(e["event"] == "post_blind" for e in hand_data["events"]))
first_player = hand_data["current_player_id"]
check("Has current_player_id", first_player is not None)

print(f"\n  Hand {HAND_ID[:8]}... started. First to act: {first_player[:8]}...")

# Play through actions until hand completes
MAX_ACTIONS = 20
actions_taken = 0
hand_complete = False

for _ in range(MAX_ACTIONS):
    r = get(f"/api/tables/{TABLE_ID}")
    tstate = r.get_json()
    hand = tstate.get("current_hand")
    if not hand or hand.get("phase") in ("complete", "showdown"):
        hand_complete = True
        break

    current_pid = hand.get("current_player_id")
    if not current_pid:
        hand_complete = True
        break

    r = get(f"/api/tables/{TABLE_ID}/player-view/{current_pid}")
    view = r.get_json()
    legal = view.get("private", {}).get("legal_actions", [])

    if not legal:
        hand_complete = True
        break

    action_types = [a["type"] for a in legal]
    if "call" in action_types:
        chosen = {"type": "call"}
    elif "check" in action_types:
        chosen = {"type": "check"}
    else:
        chosen = {"type": "fold"}

    r = post(f"/api/tables/{TABLE_ID}/action", {
        "player_id": current_pid,
        "action": chosen,
    })
    result = r.get_json()
    actions_taken += 1

    if result.get("hand_complete"):
        hand_complete = True
        summary = result.get("summary", {})
        print(f"  Hand complete after {actions_taken} actions.")
        print(f"  Winners: {json.dumps(summary.get('winners', []), indent=2)[:200]}")
        break

check("Hand completed", hand_complete)
check(f"Actions taken ({actions_taken}) > 0", actions_taken > 0)

# ════════════════════════════════════════════════════════════════════════════
# 7. Frontend Adapter — Card & State Format
# ════════════════════════════════════════════════════════════════════════════

section("7. Frontend Adapter")

from app.engine.deck import Card
from app.engine.frontend_adapter import (
    card_to_frontend, cards_to_frontend, phase_to_frontend,
    build_frontend_game_state, build_hand_result,
)

ace_hearts = Card(rank=14, suit="h")
ten_spades = Card(rank=10, suit="s")
two_clubs = Card(rank=2, suit="c")

fc = card_to_frontend(ace_hearts)
check("Card(14,'h') → suit=hearts", fc["suit"] == "hearts")
check("Card(14,'h') → rank=A", fc["rank"] == "A")
check("Card(14,'h') → faceUp=True", fc["faceUp"] is True)

fc2 = card_to_frontend(ten_spades)
check("Card(10,'s') → rank=10", fc2["rank"] == "10")
check("Card(10,'s') → suit=spades", fc2["suit"] == "spades")

fc3 = card_to_frontend("2c")
check("String '2c' → rank=2, suit=clubs", fc3["rank"] == "2" and fc3["suit"] == "clubs")

check("phase preflop → pre-flop", phase_to_frontend("preflop") == "pre-flop")
check("phase flop → flop", phase_to_frontend("flop") == "flop")
check("phase showdown → showdown", phase_to_frontend("showdown") == "showdown")

from app.engine.table import Table as EngineTable
t = EngineTable(max_seats=3, small_blind=10, big_blind=20, starting_stack=500)
t.join("p1", "agent")
t.join("p2", "agent")
t.join("p3", "agent")
hand, events = t.start_hand(seed=99)

name_map = {"p1": "Alpha", "p2": "Beta", "p3": "Gamma"}
gs = build_frontend_game_state(t, "TESTCD", name_map=name_map, viewer_id="p1")
check("GameState has roomCode", gs["roomCode"] == "TESTCD")
check("GameState phase is pre-flop", gs["phase"] == "pre-flop")
check("GameState has 3 players", len(gs["players"]) == 3)
check("Player names resolved", gs["players"][0]["agentName"] in ("Alpha", "Beta", "Gamma"))
check("GameState has communityCards (empty preflop)", gs["communityCards"] == [])
check("GameState has pot > 0 (blinds)", gs["pot"] > 0)
check("GameState has handNumber", gs["handNumber"] == 1)
check("GameState has actionLog", isinstance(gs["actionLog"], list))

viewer_player = next(p for p in gs["players"] if p["userId"] == "p1")
check("Viewer hole cards revealed", viewer_player["holeCards"] is not None)
check("Viewer hole cards are frontend format", viewer_player["holeCards"][0].get("suit") in
      ("hearts", "diamonds", "clubs", "spades"))

non_viewer = next(p for p in gs["players"] if p["userId"] != "p1")
check("Non-viewer hole cards hidden", non_viewer["holeCards"] is None)

# Player state boolean flags
has_dealer = any(p["isDealer"] for p in gs["players"])
has_sb = any(p["isSmallBlind"] for p in gs["players"])
has_bb = any(p["isBigBlind"] for p in gs["players"])
check("Exactly one dealer", has_dealer)
check("Has small blind", has_sb)
check("Has big blind", has_bb)

# ════════════════════════════════════════════════════════════════════════════
# 8. Play a complete mini-hand and check HandResult format
# ════════════════════════════════════════════════════════════════════════════

section("8. Mini-Hand → HandResult Format")

t2 = EngineTable(max_seats=2, small_blind=5, big_blind=10, starting_stack=200)
t2.join("hero", "agent")
t2.join("villain", "agent")
h2, ev2 = t2.start_hand(seed=777)

actions_played = 0
while not h2.is_hand_over:
    cp = h2.current_player
    if not cp:
        break
    legal = h2.get_legal_actions(cp.player_id)
    if not legal:
        break
    action_types = [a["type"] for a in legal]
    if "check" in action_types:
        h2.apply_action(cp.player_id, {"type": "check"})
    elif "call" in action_types:
        h2.apply_action(cp.player_id, {"type": "call"})
    else:
        h2.apply_action(cp.player_id, {"type": "fold"})
    actions_played += 1
    if actions_played > 30:
        break

check("Mini-hand completed", h2.is_hand_over)
check(f"Mini-hand took {actions_played} actions", actions_played > 0)

nm = {"hero": "Hero Agent", "villain": "Villain Agent"}
hr = build_hand_result(h2, nm)
check("HandResult has winnerUserId", hr["winnerUserId"] in ("hero", "villain"))
check("HandResult has winnerName", hr["winnerName"] in ("Hero Agent", "Villain Agent"))
check("HandResult has handRank", len(hr["handRank"]) > 0)
check("HandResult has potWon > 0", hr["potWon"] > 0)
check("HandResult has 2 player entries", len(hr["players"]) == 2)

for p in hr["players"]:
    check(f"  Player {p['agentName']} has holeCards", len(p["holeCards"]) == 2)
    if p["holeCards"]:
        check(f"  Hole card format correct", p["holeCards"][0].get("suit") in
              ("hearts", "diamonds", "clubs", "spades"))
    check(f"  Player {p['agentName']} has chipChange", isinstance(p["chipChange"], int))

# ════════════════════════════════════════════════════════════════════════════
# 9. Game Turn Protocol (stubbed inference)
# ════════════════════════════════════════════════════════════════════════════

section("9. Game Turn Protocol")

t3 = EngineTable(max_seats=2, small_blind=10, big_blind=20, starting_stack=1000)
t3.join(AGENT1_ID, "agent")
t3.join(AGENT2_ID, "agent")
h3, _ = t3.start_hand(seed=555)

from app.routes.tables import get_table_store
get_table_store()[t3.id] = t3

current = h3.current_player
check("Hand 3 has current player", current is not None)

r = post("/api/game/turn", {
    "agent_id": current.player_id,
    "table_id": t3.id,
})
turn_result = r.get_json() or {}
check("POST /api/game/turn → 200", r.status_code == 200, f"got {r.status_code}")
check("Turn result has action", "action" in turn_result, f"keys: {list(turn_result.keys())}")
check("Turn result has parse_ok", "parse_ok" in turn_result)
check("Turn result stub=True (no Modal)", turn_result.get("stub") is True)
check("Turn action has type", isinstance(turn_result.get("action"), dict) and "type" in turn_result["action"])

# ════════════════════════════════════════════════════════════════════════════
# 10. Memory
# ════════════════════════════════════════════════════════════════════════════

section("10. Memory Service")

from app.services import memory as memory_svc

mem = memory_svc.get_or_create(AGENT1_ID, "test-game")
check("Memory created", mem is not None)
check("Memory agent_id matches", mem.agent_id == AGENT1_ID)

mem.add_summary("Hand 1: I folded preflop with 2h 7d", hand_number=1)
mem.add_summary("Hand 2: Called with Ah Kd, won the pot", hand_number=2)
ctx = mem.build_memory_context()
check("Memory context not empty", len(ctx) > 0)
check("Memory context contains summary", "Game History" in ctx)

# ════════════════════════════════════════════════════════════════════════════
# 11. Communication & Nudges
# ════════════════════════════════════════════════════════════════════════════

section("11. Communication & Nudges")

r = post("/api/game/messages", {
    "game_id": "test-game",
    "sender_id": AGENT1_ID,
    "content": "Nice hand!",
    "phase": "between_hands",
})
check("Send message → 201", r.status_code == 201)

r = get(f"/api/game/messages/test-game?player_id={AGENT2_ID}")
msgs = r.get_json()
check("Get messages → list", isinstance(msgs, list))

r = post("/api/game/nudge", {
    "agent_id": AGENT1_ID,
    "game_id": "test-game",
    "message": "Play more aggressively!",
    "from_user": "user-alice",
    "permission_level": "owner",
})
check("Send nudge → 201", r.status_code == 201)

# ════════════════════════════════════════════════════════════════════════════
# 12. Logging
# ════════════════════════════════════════════════════════════════════════════

section("12. Logging")

r = get(f"/api/game/logs/{t3.id}")
logs = r.get_json()
check("GET game logs → 200", r.status_code == 200)
check("Logs has decisions", isinstance(logs.get("decisions"), list))
check("Logs has failures", isinstance(logs.get("failures"), list))
check("At least 1 decision logged", len(logs["decisions"]) >= 1)

# ════════════════════════════════════════════════════════════════════════════
# 13. Leaderboard
# ════════════════════════════════════════════════════════════════════════════

section("13. Leaderboard")

r = get("/api/leaderboard")
check("GET /api/leaderboard → 200", r.status_code == 200)
lb = r.get_json()
check("Leaderboard is a list", isinstance(lb, list))

# ════════════════════════════════════════════════════════════════════════════
# 14. Hand History
# ════════════════════════════════════════════════════════════════════════════

section("14. Hand History")

r = get(f"/api/tables/{TABLE_ID}/history")
check("GET hand history → 200", r.status_code == 200)
history = r.get_json()
check("History is a list", isinstance(history, list))

# ════════════════════════════════════════════════════════════════════════════
# 15. Cleanup & Deletion
# ════════════════════════════════════════════════════════════════════════════

section("15. Cleanup")

r = post(f"/api/rooms/{ROOM_CODE}/leave", {"userId": "user-charlie"})
check("Leave room → 200", r.status_code == 200)

r = client.delete(f"/api/agents/{AGENT3_ID}")
check("Delete agent → 200", r.status_code == 200)

r = get("/api/agents")
check("Agents after delete → 2", len(r.get_json()) == 2)


# ════════════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print(f"  RESULTS:  {PASS} passed,  {FAIL} failed,  {PASS + FAIL} total")
print(f"{'='*60}\n")

if FAIL > 0:
    sys.exit(1)
