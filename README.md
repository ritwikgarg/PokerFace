# PokerFace

A real-time **Texas Hold'em** game where you AI agents play against each other. Create custom agents (personality, risk, model), host or join rooms with a code, and play full hands with live updates over WebSockets. The backend runs a trusted game engine and LLM inference (e.g. via Modal).

---

## Features

- **Custom AI agents** — Configure name, play style (TAG/LAG/etc.), risk tolerance, deception, and base LLM. Agents are synced to the backend and used in games.
- **Rooms** — Create a room (get a 6-character code) or join with a code. Lobby with ready-up; host starts when everyone is ready.
- **Live poker table** — No-limit Hold'em with pot, community cards (flop/turn/river), player seats, bet-this-round display, and fold/check/call/raise/all-in actions. Real-time state via Socket.IO.
- **Credits & leaderboard** — User credits for creating agents and sending in-game prompts; leaderboard of agent performance (optional backend).
- **Backend engine** — Deterministic rules, hand evaluation, side pots, replayable hand history. Optional Modal GPU workers for LLM inference.

---

## Tech Stack

| Layer        | Stack |
|-------------|--------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind, Framer Motion, Socket.IO client, NextAuth (GitHub), Prisma (Postgres), Zustand |
| **Backend**  | Flask, Flask-SocketIO (eventlet/threading), Python 3.x, in-memory stores (rooms, agents, tables) |
| **Database** | PostgreSQL (Prisma; used for users, agents, rooms, credits) |
| **Optional** | Modal (GPU inference), Hugging Face (models) |

---

## Project Structure

```
agent-poker/
├── frontend/          # Next.js app (dashboard, agents, rooms, poker table UI)
├── backend/           # Flask API + Socket.IO game engine and rooms
├── finetuning/        # Optional: Qwen fine-tuning on PokerBench via Modal
└── README.md          # This file
```

- **Frontend**: `frontend/` — App Router, `/dashboard`, `/room/[code]`, `/room/create`, `/room/join`, API routes under `/api/*`. See `frontend/README.md` for scripts.
- **Backend**: `backend/` — Flask app, game engine under `app/engine/`, rooms and sockets under `app/routes/` and `app/sockets/`. See `backend/README.md` for architecture and API.
- **Finetuning**: `finetuning/` — Modal-based training and eval. See `finetuning/README.md`.

---

## Prerequisites

- **Node.js** 20+ and **npm** (or yarn/pnpm)
- **Python** 3.10+
- **PostgreSQL** (for Prisma; e.g. local or Supabase)
- **GitHub OAuth app** (for NextAuth) — [GitHub Developer Settings](https://github.com/settings/developers)

---

## Environment Setup

### Frontend (Next.js)

Copy the example env and fill in values:

```bash
cd frontend
cp .env.example .env.local
```

Edit `.env.local`:

```env
# GitHub OAuth
GITHUB_ID=your_github_oauth_app_id
GITHUB_SECRET=your_github_oauth_app_secret

# NextAuth
AUTH_SECRET=generate_with_openssl_rand_base64_32
AUTH_URL=http://localhost:3000

# Backend (Flask + Socket.IO)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=http://localhost:8000

# Database (Prisma)
DATABASE_URL="postgresql://user:password@host:5432/dbname"
```

Generate `AUTH_SECRET`:

```bash
openssl rand -base64 32
```

### Backend (Flask)

Backend can run with no env (defaults). Optional:

- `.env` in `backend/` with `RENDER=1` if you need eventlet for production-style async.
- Modal/HF keys only if you use inference or finetuning.

---

## Quick Start

### 1. Database (Postgres)

Create a Postgres database and set `DATABASE_URL` in `frontend/.env.local`.

### 2. Frontend

```bash
cd frontend
npm install
npx prisma generate
npx prisma db push   # or migrate, as needed
npm run dev
```

App: [http://localhost:3000](http://localhost:3000).

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
python run.py
```

API + WebSockets: [http://localhost:8000](http://localhost:8000).

### 4. Play

1. Open the app and sign in with GitHub.
2. Create an agent (Dashboard → create agent: name, play style, risk, model, etc.).
3. Create a room (pick that agent) and copy the room code, or join an existing room with a code.
4. In the lobby, ready up; host clicks **Start game** when everyone is ready.
5. Play on the poker table: use Fold / Check / Call / Raise / All-in when it’s your turn. Community cards and pot update in real time.

---

## Main Flows

- **Start game** — No REST call. The frontend emits Socket.IO `start-game` with `{ roomCode, userId }`. The backend creates the table, posts blinds, deals, and emits `game-started` (with per-viewer state so each client sees their own hole cards). The UI switches from lobby to the poker table.
- **Actions** — Frontend emits `player-action` with `{ roomCode, userId, action, amount? }`. Backend validates, applies the action, and broadcasts `game:player_acted`, `game:phase_changed`, `game:community_cards_revealed`, `game:hand_result`, etc.
- **Rooms** — Created via `POST /api/rooms` (Next.js API route that syncs the agent to the Flask backend and then calls the backend’s `POST /api/rooms`). Join via `POST /api/rooms/[code]` (join in Flask; if the room is missing there, the route can rehydrate from Prisma and retry).

---

## Docs

- **Backend**: [backend/README.md](backend/README.md) — Game engine, orchestrator, Socket.IO events, API reference.
- **Frontend**: [frontend/README.md](frontend/README.md) — Next.js scripts and overview.
- **Finetuning**: [finetuning/README.md](finetuning/README.md) — PokerBench training and Modal.

---

## License

See repository license file if present.
