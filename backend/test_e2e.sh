#!/usr/bin/env bash
# End-to-end test: creates 2 agents, seats them, deals a hand, and
# runs each agent's turn through the full Modal inference pipeline.
#
# Prerequisites:
#   1. Flask server running:  cd backend && source .venv/bin/activate && python run.py
#   2. Modal app deployed:    modal deploy app/services/inference_modal.py
#
# Usage:  chmod +x test_e2e.sh && ./test_e2e.sh

set -euo pipefail
BASE="http://localhost:8000/api"

blue()  { printf "\n\033[1;34m=== %s ===\033[0m\n" "$1"; }
green() { printf "\033[0;32m%s\033[0m\n" "$1"; }
red()   { printf "\033[0;31m%s\033[0m\n" "$1"; }

# ── 1. Health check ─────────────────────────────────────────────────────────
blue "Health check"
curl -s "$BASE/health" | python3 -m json.tool

# ── 2. Create two agents ────────────────────────────────────────────────────
blue "Creating Agent 1 (TAG, Mistral 7B)"
AGENT1=$(curl -s -X POST "$BASE/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SharkBot",
    "baseLLM": "gpt-4o-mini",
    "riskTolerance": 60,
    "deception": 30,
    "playStyle": "tight-aggressive",
    "previousGamesHistory": 2,
    "temperature": 0.7,
    "personalityPrompt": "You are a calculated poker shark. Make precise, mathematical decisions."
  }')
echo "$AGENT1" | python3 -m json.tool
AGENT1_ID=$(echo "$AGENT1" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
green "Agent 1 ID: $AGENT1_ID"

blue "Creating Agent 2 (LAG, Mistral 7B)"
AGENT2=$(curl -s -X POST "$BASE/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BluffMaster",
    "baseLLM": "gpt-4o-mini",
    "riskTolerance": 80,
    "deception": 70,
    "playStyle": "loose-aggressive",
    "previousGamesHistory": 1,
    "temperature": 0.9,
    "personalityPrompt": "You are an aggressive bluffer. Apply maximum pressure at every opportunity."
  }')
echo "$AGENT2" | python3 -m json.tool
AGENT2_ID=$(echo "$AGENT2" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
green "Agent 2 ID: $AGENT2_ID"

# ── 3. Create a table ──────────────────────────────────────────────────────
blue "Creating table (heads-up, 5/10 blinds)"
TABLE=$(curl -s -X POST "$BASE/tables" \
  -H "Content-Type: application/json" \
  -d '{"max_seats": 2, "small_blind": 5, "big_blind": 10, "starting_stack": 1000}')
echo "$TABLE" | python3 -m json.tool
TABLE_ID=$(echo "$TABLE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
green "Table ID: $TABLE_ID"

# ── 4. Seat both agents ────────────────────────────────────────────────────
blue "Seating agents"
curl -s -X POST "$BASE/tables/$TABLE_ID/join" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\": \"$AGENT1_ID\"}" | python3 -m json.tool

curl -s -X POST "$BASE/tables/$TABLE_ID/join" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\": \"$AGENT2_ID\"}" | python3 -m json.tool

# ── 5. Deal a hand ─────────────────────────────────────────────────────────
blue "Starting hand"
HAND=$(curl -s -X POST "$BASE/tables/$TABLE_ID/start-hand" \
  -H "Content-Type: application/json" \
  -d '{"seed": 42}')
echo "$HAND" | python3 -m json.tool
CURRENT=$(echo "$HAND" | python3 -c "import sys,json; print(json.load(sys.stdin)['current_player_id'])")
green "First to act: $CURRENT"

# ── 6. Run turns until hand completes ──────────────────────────────────────
for TURN_NUM in $(seq 1 20); do
  blue "Turn $TURN_NUM — Agent: ${CURRENT:0:8}..."

  TURN_RESULT=$(curl -s -X POST "$BASE/game/turn" \
    -H "Content-Type: application/json" \
    -d "{\"agent_id\": \"$CURRENT\", \"table_id\": \"$TABLE_ID\"}")
  echo "$TURN_RESULT" | python3 -m json.tool

  ACTION_TYPE=$(echo "$TURN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['action']['type'])")
  ACTION_AMOUNT=$(echo "$TURN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['action'].get('amount') or '')")
  STUB=$(echo "$TURN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stub', False))")

  if [ "$STUB" = "True" ]; then
    red "WARNING: Got stub response (Modal not connected)"
  fi

  TABLE_TALK=$(echo "$TURN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('table_talk', ''))" 2>/dev/null)
  green "Action: $ACTION_TYPE ${ACTION_AMOUNT}"
  if [ -n "$TABLE_TALK" ]; then
    printf "\033[1;33m  💬 \"%s\"\033[0m\n" "$TABLE_TALK"
  fi

  # Apply the action to the engine
  blue "Applying action to engine"
  if [ -n "$ACTION_AMOUNT" ]; then
    ACTION_JSON="{\"player_id\": \"$CURRENT\", \"action\": {\"type\": \"$ACTION_TYPE\", \"amount\": $ACTION_AMOUNT}}"
  else
    ACTION_JSON="{\"player_id\": \"$CURRENT\", \"action\": {\"type\": \"$ACTION_TYPE\"}}"
  fi

  ENGINE_RESULT=$(curl -s -X POST "$BASE/tables/$TABLE_ID/action" \
    -H "Content-Type: application/json" \
    -d "$ACTION_JSON")
  echo "$ENGINE_RESULT" | python3 -m json.tool

  HAND_COMPLETE=$(echo "$ENGINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hand_complete', False))")

  if [ "$HAND_COMPLETE" = "True" ]; then
    green "Hand complete!"
    break
  fi

  CURRENT=$(echo "$ENGINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('next_player_id', ''))")
  if [ -z "$CURRENT" ] || [ "$CURRENT" = "None" ]; then
    green "No next player — hand over."
    break
  fi
done

# ── 7. Check logs ──────────────────────────────────────────────────────────
blue "Game logs"
curl -s "$BASE/game/logs/$TABLE_ID" | python3 -m json.tool

# ── 8. Table talk (all banter from the game) ─────────────────────────────
blue "Table Talk"
curl -s "$BASE/game/messages/$TABLE_ID" | python3 -m json.tool

# ── 9. Check workers ──────────────────────────────────────────────────────
blue "Worker status"
curl -s "$BASE/game/workers?table_id=$TABLE_ID" | python3 -m json.tool

# ── 10. File logs (game log + prompt log) ──────────────────────────────────
blue "File logs"
GAME_LOG=$(ls -t logs/game_*.log 2>/dev/null | head -1)
PROMPT_LOG=$(ls -t logs/prompts_*.log 2>/dev/null | head -1)

if [ -n "$GAME_LOG" ]; then
  printf "\n\033[1;33m── Game Log: %s ──\033[0m\n" "$GAME_LOG"
  cat "$GAME_LOG"
else
  red "No game log files found in logs/"
fi

if [ -n "$PROMPT_LOG" ]; then
  printf "\n\033[1;33m── Prompt Log: %s (first 200 lines) ──\033[0m\n" "$PROMPT_LOG"
  head -200 "$PROMPT_LOG"
else
  red "No prompt log files found in logs/"
fi

blue "Done!"
