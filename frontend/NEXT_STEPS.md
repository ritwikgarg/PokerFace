# 🎯 Next Steps - Frontend Complete, Backend Integration Ready

## ✅ Frontend Status: **COMPLETE**
All poker UI components are built and ready for integration:
- ✅ 10 poker components (cards, seats, pot, action panel, etc.)
- ✅ Card visibility system (your cards face-up, opponents' face-down)
- ✅ Agent behavior prompt system
- ✅ Full action buttons and betting controls
- ✅ Real-time action log
- ✅ Hand result modal with chip tracking
- ✅ Authentication system (NextAuth.js + GitHub OAuth)

---

## 🔧 REMAINING WORK (In Priority Order)

### 1. **CRITICAL: Set Up GitHub OAuth** 
**Status**: ❌ Blocked on user action
**Time**: 5 minutes

```bash
# Go to: https://github.com/settings/developers
# Click "New OAuth App"

# Fill in:
- Application name: "Agent Poker"
- Homepage URL: "http://localhost:3000"
- Authorization callback URL: "http://localhost:3000/api/auth/callback/github"

# Copy credentials into .env.local:
GITHUB_ID=your_client_id_here
GITHUB_SECRET=your_client_secret_here
```

### 2. **CRITICAL: Set Up Database**
**Status**: ❌ Blocked on user action
**Time**: 5-10 minutes

**Option A: Supabase (Recommended)**
```bash
# 1. Go to https://supabase.com
# 2. Create new project
# 3. Copy connection string to .env.local:
DATABASE_URL="postgresql://user:password@host:5432/postgres"

# 4. Run migrations:
npx prisma migrate dev --name init
```

**Option B: Local PostgreSQL**
```bash
# 1. Install PostgreSQL locally
# 2. Create database:
createdb agent_poker

# 3. Set .env.local:
DATABASE_URL="postgresql://localhost/agent_poker"

# 4. Run migrations:
npx prisma migrate dev --name init
```

### 3. **Wire Up WebSocket Real-Time Updates**
**Status**: 🟡 Needs backend implementation
**Time**: 2-3 hours
**File**: `src/hooks/use-game-socket.ts` (create this)

```typescript
// What your hook should do:
// 1. Connect to backend WebSocket
// 2. Listen for "gameUpdated" → update gameStore
// 3. Listen for "handResult" → show modal
// 4. Emit "playerAction" when user acts
// 5. Emit "agentPrompt" when user modifies agent behavior
```

**Example of hook you need to create**:
```typescript
import { useEffect, useRef } from 'react';
import io, { Socket } from 'socket.io-client';

export function useGameSocket(roomCode: string) {
  const socket = useRef<Socket | null>(null);

  useEffect(() => {
    socket.current = io(process.env.NEXT_PUBLIC_WS_URL, {
      query: { roomCode },
      auth: { /* token from session */ }
    });

    return () => {
      socket.current?.disconnect();
    };
  }, [roomCode]);

  return { socket: socket.current };
}
```

### 4. **Update Main Game Room Page**
**Status**: 🟡 Partially done
**Time**: 1 hour
**File**: `src/app/room/[code]/page.tsx`

Copy the pattern from `src/app/room/example-game-integration.tsx`:
- Import PokerTable component
- Set up GameSocket hook
- Wire action handlers
- Pass to PokerTable with gameState

### 5. **Create Game Lobby**
**Status**: ❌ Not started
**Time**: 1-2 hours
**File**: `src/app/lobby/page.tsx`

Features needed:
- [ ] List rooms available to join
- [ ] Create new room with settings (buy-in, AI difficulty, etc.)
- [ ] Show players in room before game starts
- [ ] Configure your agent (name, style, risk tolerance)
- [ ] Start game when all players ready

### 6. **Create Leaderboard**
**Status**: ❌ Not started
**Time**: 1 hour
**File**: `src/app/leaderboard/page.tsx`

Display:
- [ ] Total winnings/losses per player
- [ ] Win rate
- [ ] Average pot won
- [ ] Agent performance stats
- [ ] Sorting/filtering options

---

## 📋 Backend Requirements

### **WebSocket Events Frontend Expects**

```typescript
// Backend sends these to frontend:

// 1. Game state updates (whenever game changes)
socket.emit('gameUpdated', {
  roomCode: string,
  phase: 'pre-flop' | 'flop' | 'turn' | 'river' | 'showdown',
  communityCards: Card[],
  pot: number,
  currentBet: number,
  players: PlayerState[],
  dealerIndex: number,
  activePlayerIndex: number,
  handNumber: number,
  actionLog: ActionLogEntry[]
});

// 2. Hand result when showdown complete
socket.emit('handResult', {
  winnerUserId: string,
  winnerName: string,
  handRank: string,
  potWon: number,
  players: [{
    userId: string,
    agentName: string,
    holeCards: [Card, Card],
    handRank: string,
    chipChange: number
  }]
});
```

### **WebSocket Events Backend Should Listen For**

```typescript
// Frontend sends these to backend:

// 1. Player action
socket.on('playerAction', ({ 
  roomCode: string, 
  userId: string, 
  action: 'fold' | 'check' | 'call' | 'raise' | 'all-in', 
  amount?: number 
}));

// 2. Agent prompt (behavior modification)
socket.on('agentPrompt', ({ 
  roomCode: string, 
  userId: string, 
  prompt: string 
}));

// 3. Player ready for next hand
socket.on('readyForNextHand', ({ roomCode: string }));
```

---

## 🧪 Testing Checklist

After completing above steps:

- [ ] Run `npm run dev` locally
- [ ] Test GitHub OAuth login
- [ ] Create a room
- [ ] Start a 2-player game (you + 1 AI)
- [ ] See your cards face-up, opponent's face-down
- [ ] Click action buttons (fold, check, call, raise)
- [ ] Action log updates in real-time
- [ ] Type agent prompt and see it send to backend
- [ ] Game shows showdown modal with results
- [ ] Multiple players can join same room
- [ ] Chips update correctly at end of hand

---

## 📦 Additional Dependencies (Already In Your package.json)

Frontend needs these already installed:
- ✅ next-auth
- ✅ zustand
- ✅ framer-motion
- ✅ shadcn/ui
- ✅ socket.io-client
- ✅ react-hook-form
- ✅ zod
- ✅ lucide-react

Backend will need:
- socket.io
- prisma
- next-auth
- jsonwebtoken

---

## 📚 Key Files Reference

### Frontend Components
| File | Purpose |
|------|---------|
| `poker-table.tsx` | Main container |
| `player-seat.tsx` | Individual player display |
| `poker-card.tsx` | Card rendering |
| `community-cards.tsx` | Board cards |
| `pot-display.tsx` | Chip display |
| `game-action-panel.tsx` | Your action buttons + agent prompt |
| `action-log.tsx` | Real-time action history |
| `hand-result-modal.tsx` | Showdown results |

### Game Logic
| File | Purpose |
|------|---------|
| `game-store.ts` | Zustand state management |
| `use-game-socket.ts` | WebSocket connection (NEEDS TO BE CREATED) |
| `auth.ts` | NextAuth configuration |

---

## 🚀 Local Development

```bash
# 1. Install dependencies
npm install

# 2. Set up .env.local (copy from .env.local.example)
cp .env.local.example .env.local
# Then edit with real values from:
# - GitHub OAuth app
# - Database connection string
# - Backend WebSocket URL

# 3. Generate Prisma client
npx prisma generate

# 4. Run migrations
npx prisma migrate dev --name init

# 5. Start dev server
npm run dev

# 6. Open http://localhost:3000
```

---

## 🎯 Estimated Timeline

- **Auth Setup**: 5 min
- **Database Setup**: 10 min  
- **WebSocket Hook**: 1-2 hours
- **Game Room Page**: 1 hour
- **Lobby Page**: 1-2 hours
- **Leaderboard**: 1 hour
- **Testing & Fixes**: 2-3 hours

**Total: 7-9 hours** for full working game

---

## 💡 Pro Tips

1. **Test card visibility** - Make sure only YOUR cards show face-up in browser dev tools
2. **Test blinds logic** - Verify dealer position rotates, blinds are set correctly
3. **Test pot calculations** - Verify pot and player bets sum correctly
4. **Test agent prompts** - Make sure prompts actually reach backend and influence agent behavior
5. **Handle reconnection** - If user refreshes, should rejoin without losing game state
6. **Spectator mode** - Later: allow users to watch games without playing

---

## 📞 Questions?

See `POKER_UI_GUIDE.md` for:
- Detailed component prop documentation
- Design system specifications
- Animation timings
- Responsive breakpoints
- Card visibility logic explanation

