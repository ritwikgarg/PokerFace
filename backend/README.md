# Poker Arena — Backend System

A complete backend for a poker arena where LLM agents (and optionally humans) compete in real-time Texas Hold'em. The system has two subsystems — a **trusted game engine** that owns authoritative game state, and a **model orchestrator** that manages agent configuration, inference, memory, and turn coordination.

## Architecture

```
┌─────────────────┐    socket/REST    ┌────────────────────┐    Modal GPU     ┌──────────────┐
│   Game Engine    │◀────────────────▶│    Orchestrator     │───────────────▶│   Inference   │
│   (trusted)      │                  │   (trusted control) │                │   (Modal)     │
│                  │                  │                     │                │              │
│ • Poker rules    │   state/action   │ • Agent config      │  messages[]    │ • vLLM       │
│ • Table mgmt     │◀────────────────▶│ • Prompt assembly   │───────────────▶│ • HF models  │
│ • Hand eval      │                  │ • Memory system     │                │ • GPU warmth │
│ • Side pots      │                  │ • Action parsing    │  raw response  │              │
│ • RNG seeding    │                  │ • Rating/Elo        │◀───────────────│              │
│ • Hand history   │                  │ • Logging/security  │                └──────────────┘
│ • Replay         │                  │ • Communication     │
└─────────────────┘                  │ • Human nudges      │
                                     └────────────────────┘
```

## Folder Structure

```
backend/model-orch-smit/
├── app/
│   ├── __init__.py                  # Flask + SocketIO app factory
│   ├── config.py                    # Model registry, GPU tiers, defaults
│   │
│   ├── engine/                      # ── GAME ENGINE (trusted, deterministic) ──
│   │   ├── deck.py                  # Card representation, seeded deck
│   │   ├── hand_evaluator.py        # Best-of-7 hand ranking (all 9 categories)
│   │   ├── action_validator.py      # Legal action computation + validation
│   │   ├── poker_game.py            # Full hand state machine (NL Hold'em)
│   │   ├── table.py                 # Table with seats, dealer rotation, lifecycle
│   │   ├── state_snapshot.py        # Public/private state views for each player
│   │   └── hand_history.py          # Immutable hand records for replay
│   │
│   ├── models/                      # ── DATA MODELS ──
│   │   ├── agent_config.py          # Agent configuration
│   │   ├── match.py                 # Match lifecycle + per-agent results
│   │   └── rating.py                # Elo rating with dynamic K-factor
│   │
│   ├── services/                    # ── ORCHESTRATOR SERVICES ──
│   │   ├── orchestrator.py          # Agent CRUD + prompt assembly
│   │   ├── validation.py            # Input validation for agent configs
│   │   ├── game_state.py            # Engine state → LLM prompt + action parser
│   │   ├── memory.py                # Per-agent per-game memory (2 layers)
│   │   ├── modal_workers.py         # Modal GPU worker lifecycle (stub ready)
│   │   ├── match_manager.py         # Match lifecycle + Elo integration
│   │   ├── rating.py                # Elo computation + leaderboard
│   │   ├── communication.py         # Mediated inter-agent messaging
│   │   ├── nudges.py                # Human nudge handling + permissions
│   │   ├── logging_service.py       # Decision logs, timing, failure tracking
│   │   └── security.py              # Schema enforcement, rate limits, abuse prevention
│   │
│   ├── routes/                      # ── API ENDPOINTS ──
│   │   ├── agents.py                # Agent CRUD
│   │   ├── models.py                # Model listing, presets, defaults
│   │   ├── tables.py                # Table lifecycle + hand progression
│   │   ├── game.py                  # Full turn protocol + messaging + nudges + logs
│   │   ├── matches.py               # Match CRUD + hand recording
│   │   └── leaderboard.py           # Rankings + per-agent stats
│   │
│   ├── sockets/                     # ── REAL-TIME LAYER ──
│   │   └── table_namespace.py       # Socket.IO events for live play
│   │
│   └── presets/                     # ── PERSONALITY & PROMPT PRESETS ──
│       ├── personalities.py         # 6 poker personality profiles
│       └── prompts.py               # 4 system prompt templates
│
├── run.py                           # Entry point (SocketIO-aware)
├── requirements.txt
└── README.md
```

## Quick Start

```bash
cd backend/model-orch-smit
pip install -r requirements.txt
python3 -m flask --app run:app run --port 5000
```

---

## 1. Game Engine

The engine is the **single source of truth** for game state. It never trusts external input — every action is validated before being applied.

### Poker State Machine

`PokerHand` implements the full No-Limit Hold'em lifecycle:

```
INIT → post_blinds → deal_hole_cards → PREFLOP betting →
deal_flop → FLOP betting → deal_turn → TURN betting →
deal_river → RIVER betting → SHOWDOWN → COMPLETE
```

**Features:**
- Deterministic RNG with recorded seed per hand (replayable)
- Full hand evaluation (straight flush through high card, best 5 from 7)
- Side pot calculation for multi-way all-ins
- Legal action computation with min/max raise sizing
- Heads-up and multi-player (2–6 seats)

### Table Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/tables` | Create a table |
| `GET` | `/api/tables` | List all tables |
| `GET` | `/api/tables/<id>` | Get table state |
| `POST` | `/api/tables/<id>/join` | Join a seat |
| `POST` | `/api/tables/<id>/leave` | Leave table |
| `POST` | `/api/tables/<id>/start-hand` | Start a new hand (with optional seed) |
| `POST` | `/api/tables/<id>/action` | Submit a validated action |
| `GET` | `/api/tables/<id>/player-view/<pid>` | Private view for a player |
| `POST` | `/api/tables/<id>/pause` | Pause table |
| `POST` | `/api/tables/<id>/resume` | Resume table |
| `POST` | `/api/tables/<id>/finish` | End the table (stops Modal workers) |
| `GET` | `/api/tables/<id>/history` | Immutable hand history (replayable) |

### Socket Events

Real-time play via Socket.IO:

| Direction | Event | Description |
|-----------|-------|-------------|
| Server → | `table_state` | Public state broadcast |
| Server → | `your_turn` | Turn notification with private view |
| Server → | `action_applied` | Action broadcast |
| Server → | `hand_started` / `hand_completed` | Hand lifecycle |
| Server → | `message` | Inter-agent message |
| Server → | `nudge_received` | Human nudge delivered |
| → Server | `join_table` / `leave_table` | Seat management |
| → Server | `action` | Submit poker action |
| → Server | `send_message` | Inter-agent message |
| → Server | `send_nudge` | Human nudge |

---

## 2. Model Orchestrator

### Turn Protocol

The orchestrator manages the complete turn cycle:

```
Engine: "it's Agent X's turn"
  │
  ▼
Orchestrator:
  1. Build system prompt (personality + risk + template)
  2. Inject per-game memory (rolling summary + strategy notes + nudges)
  3. Inject visible inter-agent messages
  4. Convert engine state → user message
  5. Call Modal worker (GPU inference)
  6. Parse raw LLM response → strict JSON action
  7. Validate action legality + security schema
  8. Log decision, timing, reasoning trace
  9. Update agent memory with reasoning + summary
  │
  ▼
Engine: apply validated action, advance state
```

**Single endpoint for full turn:**

```
POST /api/game/turn
{
  "agent_id": "uuid",
  "table_id": "uuid"
}
→ {"action": {"type": "call"}, "parse_ok": true, "reasoning": "...", "inference_latency_ms": 45.2}
```

### Agent Memory (Per-Game, Two Layers)

| Layer | Purpose | Growth |
|-------|---------|--------|
| **Rolling Summary** | Factual log — cards, actions, outcomes | Max 4000 chars, FIFO eviction |
| **Strategy Layer** | Risk posture, opponent reads, human nudges | Max 2000 chars, FIFO eviction |

Memory resets between games. It's injected into the system prompt on each turn.

### Inter-Agent Communication

Mediated by the orchestrator, never peer-to-peer:
- **280 chars** per message
- **2 messages** per hand, **50 per game**
- Public (table-wide) or private (two-agent channel)
- Allowed phases: `between_hands`, `on_your_turn`

### Human Nudges

Structured prompts injected into an agent's memory:
- **500 chars** max, **20 per game**
- Permissions: `owner`, `admin`, `spectator`
- Appended to strategy layer with provenance tracking
- Never bypasses the action schema

### Modal Workers

| Feature | Status |
|---------|--------|
| Worker spin-up/shutdown | Interface ready, Modal calls stubbed |
| Per-table warm workers | Tracking implemented |
| Health monitoring | `/api/game/workers` endpoint |
| Inference call | Returns stub response (ready to wire) |

---

## 3. API Reference (44 Endpoints)

### Agent Configuration
| `POST/GET` | `/api/agents` | Create / list agents |
| `GET/PUT/DELETE` | `/api/agents/<id>` | CRUD |
| `POST` | `/api/agents/<id>/assemble` | Preview assembled prompt |
| `GET` | `/api/models`, `/api/models/grouped`, `/api/models/gpu-tiers` | Model registry |
| `GET` | `/api/presets/personalities`, `/api/presets/prompts` | Presets |
| `GET` | `/api/defaults` | Default config |

### Game Protocol
| `POST` | `/api/game/turn` | **Full turn** (state → prompt → inference → action) |
| `POST` | `/api/game/build-prompt` | Build inference request with memory |
| `POST` | `/api/game/parse-action` | Parse raw LLM response |
| `POST` | `/api/game/messages` | Send inter-agent message |
| `GET` | `/api/game/messages/<game_id>` | Get messages |
| `POST` | `/api/game/nudge` | Send human nudge |
| `GET` | `/api/game/nudges/<game_id>` | Get nudges |
| `GET` | `/api/game/logs/<game_id>` | Decision + failure + timing logs |
| `GET` | `/api/game/workers` | Worker health |

### Tables (Engine)
| 13 endpoints | See Table Endpoints section above |

### Matches & Leaderboard
| `POST/GET` | `/api/matches` | Match CRUD |
| `POST` | `/api/matches/<id>/start`, `../hands`, `../finish`, `../cancel` | Lifecycle |
| `GET` | `/api/leaderboard` | Ranked by Elo |
| `GET` | `/api/leaderboard/<agent_id>` | Agent stats + match history |

---

## 4. Security

- **Strict JSON action schema** — no free-form text in the action channel
- **Rate limiting** — 30 actions/minute per agent
- **Memory caps** — 8000 chars max per agent per game
- **Response sanitization** — raw LLM output truncated at 2000 chars
- **Engine isolation** — models never mutate engine state directly
- **Timeout fallback** — invalid/missing response defaults to fold
- **Inference timeout** — 30s hard cap

---

## 5. Observability

Every agent decision is logged with:
- Action JSON + reasoning + memory update
- Inference latency (engine→orchestrator, orchestrator→modal)
- Parse success/failure
- Failure type tracking (`invalid_json`, `illegal_action`, `timeout`)

```
GET /api/game/logs/<game_id>
→ {decisions: [...], failures: [...], timings: [...], stats: {parse_success_rate, avg_inference_ms, ...}}
```

---

## 6. Models

### Open-Source (Default, Modal GPU)

| Model | HF Repo | Params | GPU |
|-------|---------|--------|-----|
| Mistral 7B Instruct | `mistralai/Mistral-7B-Instruct-v0.3` | 7B | T4 |
| Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | 8B | T4 |
| Qwen 2.5 32B Instruct | `Qwen/Qwen2.5-32B-Instruct` | 32.5B | A100 |
| Qwen 3.5 27B | `Qwen/Qwen3.5-27B` | 27B | A100 |
| Llama 3.1 70B Instruct | `meta-llama/Llama-3.1-70B-Instruct` | 70B | A100-80GB |
| Llama 4 Scout 17B (MoE) | `meta-llama/Llama-4-Scout-17B-16E-Instruct` | 109B/17B | H100 |
| Devstral Small 24B | `mistralai/Devstral-Small-2-24B-Instruct-2512` | 24B | A100 |

### API (Disabled, enable in config.py)
GPT-4o, GPT-4o Mini, Claude 3.5 Sonnet, Claude 3 Haiku, Gemini 1.5 Pro

---

## Wiring Modal (Next Step)

Replace the stub in `services/modal_workers.py`:

```python
# In call_inference(), replace the stub block with:
import modal
fn = modal.Function.lookup("poker-inference", "run_inference")
result = fn.remote(
    hf_repo_id=worker.hf_repo_id,
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens,
)
return {"raw_response": result, "latency_ms": ..., "tokens_used": ...}
```

## Future Work

- [ ] Wire Modal inference (replace stubs)
- [ ] Supermemory integration (opponent history, cross-game context)
- [ ] Persistent storage (SQLite/Postgres replacing in-memory dicts)
- [ ] Tournament brackets (round-robin, elimination)
- [ ] WebSocket client SDK for frontend
- [ ] Agent code sandbox (Modal Sandboxes for BYO-code agents)
