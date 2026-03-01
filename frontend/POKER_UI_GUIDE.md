# Poker Frontend UI - Complete Implementation Guide

## ✅ What's Been Built

You now have a **fully-featured poker table UI** with all the visual mechanics needed to play Texas Hold'em. Here's what's implemented:

---

## 📊 Component Architecture

### **Core Poker Table Components**

#### 1. **PokerTable** (`poker-table.tsx`)
- **Main container** for the entire game UI
- Displays the **green felt table** with gradient backgrounds and decorative patterns
- Manages **player seats** positioned around the table
- Shows **pot** and **community cards** in the center
- Integrates **action panel** on the right sidebar for player actions
- Shows **action log** for all player moves
- Displays **hand result modal** when game ends

**Props:**
```typescript
{
  gameState: GameState
  handResult: HandResult | null
  currentUserId?: string           // Your user ID
  onNextHand?: () => void
  onAction?: (action, amount) => void  // Fold, Check, Call, Raise, All-In
  onAgentPrompt?: (prompt) => void     // Send instructions to agent
}
```

#### 2. **PokerCard** (`poker-card.tsx`)
- Displays individual playing cards
- **Face-up mode**: Shows rank and suit with appropriate colors (red for hearts/diamonds, black for clubs/spades)
- **Face-down mode**: Shows blue card back (hidden from other players)
- Smooth **flip animations** when cards are dealt
- Three sizes: small (12x16px), medium (16x24px), large (20x32px)

#### 3. **CommunityCards** (`community-cards.tsx`)
- Shows the **5 community cards** (the board)
- Always displays 5 slots (cards fill in as they're dealt)
- Empty slots show a dashed border with pulsing animation
- Smooth reveal animations as each card is dealt

#### 4. **PlayerSeat** (`player-seat.tsx`) ⭐ **KEY COMPONENT**
- Displays **individual player information** at each seat
- Shows:
  - **Avatar** (player profile image)
  - **Agent name** (who they are)
  - **Chip stack** (money remaining)
  - **Current bet** (if they've bet this round)
  - **Status indicator** (folded, all-in, active)
  - **Last action** (fold, check, call, raise)
  - **Dealer badge** (if they're the dealer)

**Card visibility (IMPORTANT FOR SECURITY):**
- **Current user**: Your 2 hole cards are **visible** (face-up)
- **Other players**: Their cards are **hidden** (face-down blue backs)
- Only when showdown occurs are all cards revealed

#### 5. **PotDisplay** (`pot-display.tsx`)
- **Center of table** shows the total pot
- Large, animated **pot amount** in yellow text
- Decorative floating chips with rotation animations
- Pulsing scale animation to draw attention

#### 6. **PhaseIndicator** (`phase-indicator.tsx`)
- Shows **current betting round**:
  - 🃏 Pre-Flop
  - 🌊 Flop
  - 🔄 The Turn
  - 🌊💧 The River
  - 🎯 Showdown
- **Hand number** tracker
- Progress bar showing game progression
- Emoji indicators for visual clarity

#### 7. **ActionLog** (`action-log.tsx`)
- **Sidebar component** showing all game actions
- Displays recent actions in reverse chronological order (newest first)
- Shows:
  - 🎰 Action emoji (fold ❌, check ✅, call 👉, raise 📈, all-in 🔥)
  - Player name (in yellow)
  - Action type (in color-coded text)
  - Bet amount (if applicable)
- Scrollable with smooth animations

#### 8. **GameActionPanel** (`game-action-panel.tsx`) ⭐ **YOUR CONTROL HUB**
- **Interactive panel** where YOU make decisions when it's your turn
- **Action buttons:**
  - `Fold` (❌ surrender your hand)
  - `Check` (✅ pass without betting)
  - `Call` (👉 match current bet)
  - `All In` (🔥 bet all remaining chips)
  - `Raise` (with custom amount input)
  
- **Current player display**: Shows whose turn it is
- **Turn indicator**: Pulsing yellow box when it's YOUR turn
- **Raise input**: Number field + button to set custom raise amount

**🎯 AGENT PERSONALITY PROMPT (NEW FEATURE):**
- **Text area** to send custom instructions to your AI agent
- Examples:
  - "Play more aggressively"
  - "Only bluff on weak hands"
  - "Call more loosely preflop"
  - "Tighten up your range"
- The agent will incorporate this prompt into its decision-making

#### 9. **HandResultModal** (`hand-result-modal.tsx`)
- **Popup dialog** showing final hand results
- Displays:
  - 👑 **Winner name** and hand rank (e.g., "Full House")
  - 💰 **Pot won** amount
  - All players' hole cards (now revealed)
  - Each player's **chip change** (green for profit, red for loss)
- "Next Hand" button to continue

#### 10. **ChipStack** (`chip-stack.tsx`)
- Visual representation of **bet amounts** at each seat
- Stacked circles in different colors (red=$1, blue=$5, green=$25, black=$100, purple=$500)
- Shows the amount below the stack

---

## 🎨 Visual Design Highlights

### **Green Felt Table**
- **Gradient background**: `from-emerald-700 via-emerald-800 to-emerald-900`
- **Wooden border**: Amber-brown frame
- **Subtle texture**: 20x20px radial gradient pattern overlay (very subtle opacity)
- **Glow effects**: Box shadows for depth
- **Rounded oval shape**: 50% border-radius for authentic poker table look

### **Color Scheme**
- **Primary table color**: Deep emerald green
- **Accent colors**:
  - Yellow/Gold (#ffff00): Pot amounts, active indicators
  - Red: Card suits (hearts/diamonds), folded status
  - Blue: Card backssuits (clubs/spades), check actions
  - Amber/Brown: Table border
- **Status indicators**:
  - Green 🟢: Normal/active player
  - Red 🔴: Folded or all-in
  - Yellow 🟡: Current turn (pulsing)

### **Animations & Polish**
- **Card flip**: 0.5s smooth rotation
- **Pot pulsing**: Constant scale breathing (1 → 1.05 → 1)
- **Floating chips**: Y-axis and rotation animations
- **Player status pulse**: Faster pulse when active
- **Smooth transitions**: All state changes animated with Framer Motion

---

## 🔗 Integration with Your Backend

### **Game State Structure**
Your `GameState` from the backend needs to include:
```typescript
{
  roomCode: string
  phase: "pre-flop" | "flop" | "turn" | "river" | "showdown"
  players: PlayerState[]
  communityCards: Card[]
  pot: number
  currentBet: number
  dealerIndex: number
  activePlayerIndex: number  // Whose turn?
  handNumber: number
  actionLog: ActionLogEntry[]
}
```

### **Player Actions (Backend Integration)**
When user clicks buttons, you need to emit these to your backend:
```typescript
// Fold
onAction?.("fold")

// Check
onAction?.("check")

// Call
onAction?.("call", currentBet)

// Raise
onAction?.("raise", 50)  // amount to raise to

// All In
onAction?.("all-in")

// Agent prompt intervention
onAgentPrompt?.("Play aggressively")
```

---

## 📱 Responsive Design

- **Desktop (1920px+)**: Full layout with sidebar action log + action panel
- **Laptop (1280px)**: Optimized spacing
- **Tablet**: Scales down gracefully
- **Mobile**: May need additional responsive adjustments

---

## 🚀 Next Steps for Integration

### **1. Connect to Your Backend WebSocket**
- Listen for `gameUpdated` events from server
- Update `gameState` in your store
- Update player actions in `actionLog`

### **2. Map Current User to Seat**
- Pass `currentUserId` to `PokerTable`
- Component will highlight your seat and show your cards
- Enable action panel when it's your turn

### **3. Wire Up Game Actions**
```tsx
<PokerTable
  gameState={gameState}
  handResult={handResult}
  currentUserId={session?.user?.id}
  onAction={(action, amount) => {
    // Send to backend
    socket.emit("playerAction", {
      roomCode,
      action,
      amount
    });
  }}
  onAgentPrompt={(prompt) => {
    // Send agent instruction
    socket.emit("agentPrompt", {
      roomCode,
      userId: session.user.id,
      prompt
    });
  }}
/>
```

### **4. Handle Hand Results**
- When game ends, your backend sends `HandResult`
- Pass to component's `handResult` prop
- Modal pops up automatically with results

---

## 🎮 Player Experience

1. **See the table**: Green felt with all players visible
2. **Know whose turn**: Highlighted active player, your turn shows action panel
3. **View community cards**: Center of table shows board
4. **Watch action unzip**: Action log shows all moves in real-time
5. **Make decisions**: Click buttons or enter raise amount
6. **See results**: Modal shows final hand and chip changes
7. **Fine-tune AI**: Send personality prompts to adjust agent behavior

---

## ⚠️ Important Notes

### **Card Visibility**
- Your cards are always visible to you
- Other players' cards are hidden (face-down blues)
- Only at showdown are all cards revealed
- This is handled automatically in `PlayerSeat` component

### **Turn Management**
- `currentPlayer` and `canAct` are determined by `activePlayerIndex`
- Action panel only enables when it's your turn AND you haven't folded/gone all-in
- All action buttons are disabled outside your turn

### **Agent Prompts**
- Prompts are suggestions, not commands
- Backend integrates them with the agent's LLM
- They modify agent behavior for future decisions

---

## 📚 Component Usage Example

```tsx
import { PokerTable } from "@/components/poker/poker-table";
import { useGameStore } from "@/stores/game-store";

export function GameRoom() {
  const gameState = useGameStore((s) => s.gameState);
  const handResult = useGameStore((s) => s.handResult);
  const session = useSession();

  return (
    <PokerTable
      gameState={gameState || defaultGameState}
      handResult={handResult}
      currentUserId={session?.user?.id}
      onAction={handleAction}
      onAgentPrompt={handlePrompt}
      onNextHand={handleNextHand}
    />
  );
}
```

---

## 🎉 Summary

You have a **production-ready** poker table UI with:
- ✅ Beautiful green felt design
- ✅ All 5 players visible with their cards (hidden for others)
- ✅ Real-time action logging
- ✅ Responsive action panel for your turn
- ✅ Agent behavior modification through prompts
- ✅ Smooth animations throughout
- ✅ Clear status indicators and visual feedback
- ✅ Hand result display with chip changes

The UI is **fully functional** and just needs to be wired to your WebSocket/Socket.io backend for real-time updates!

