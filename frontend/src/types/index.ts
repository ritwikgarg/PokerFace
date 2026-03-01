// ============================================================
// Agent Poker — Shared TypeScript Types
// ============================================================

// ---- Agent Configuration ----

export type PlayStyle =
  | "tight-aggressive"
  | "loose-aggressive"
  | "tight-passive"
  | "loose-passive";

export type LLMModel = string;

export interface AgentConfig {
  id: string;
  userId: string;
  name: string;
  riskTolerance: number; // 0–100
  deception: number; // 0–100 (bluff frequency)
  personalityPrompt: string;
  baseLLM: LLMModel;
  playStyle: PlayStyle;
  previousGamesHistory: number; // 0–3
  createdAt: string;
  updatedAt: string;
}

export type AgentConfigInput = Omit<AgentConfig, "id" | "userId" | "createdAt" | "updatedAt">;

// ---- User / Auth ----

export interface User {
  id: string;
  name: string;
  email: string;
  image: string;
  githubUsername: string;
  credits: number;
}

// ---- Leaderboard ----

export interface LeaderboardEntry {
  rank: number;
  user: Pick<User, "id" | "name" | "image" | "githubUsername">;
  agentName: string;
  gamesPlayed: number;
  winRate: number;
  totalEarnings: number;
  biggestPot: number;
}

// ---- Room ----

export interface Room {
  code: string;
  createdBy: string;
  players: RoomPlayer[];
  status: "waiting" | "in-progress" | "finished";
  maxPlayers: number;
  createdAt: string;
}

export interface RoomPlayer {
  userId: string;
  userName: string;
  userImage?: string;
  agentId: string;
  agentName: string;
  isReady: boolean;
  isHost: boolean;
}

// ---- Poker Game State ----

export type Suit = "hearts" | "diamonds" | "clubs" | "spades";
export type Rank =
  | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10"
  | "J" | "Q" | "K" | "A";

export interface Card {
  suit: Suit;
  rank: Rank;
  faceUp: boolean;
}

export type GamePhase = "pre-flop" | "flop" | "turn" | "river" | "showdown";

export type PlayerAction = "fold" | "check" | "call" | "raise" | "all-in";

export interface PlayerState {
  seatIndex: number;
  userId: string;
  agentName: string;
  userImage?: string;
  chips: number;
  currentBet: number;
  holeCards: [Card, Card] | null;
  isFolded: boolean;
  isAllIn: boolean;
  isDealer: boolean;
  isSmallBlind: boolean;
  isBigBlind: boolean;
  isActive: boolean; // currently their turn
  isThinking: boolean; // Currently thinking/deciding action
  lastAction: PlayerAction | null;
}

export interface GameState {
  roomCode: string;
  phase: GamePhase;
  communityCards: Card[];
  pot: number;
  currentBet: number;
  players: PlayerState[];
  dealerIndex: number;
  activePlayerIndex: number;
  handNumber: number;
  actionLog: ActionLogEntry[];
  promptCosts?: Record<string, number>; // Track prompt cost per player (userId -> cost)
}

export interface ActionLogEntry {
  playerName: string;
  action: PlayerAction | string;
  amount?: number;
  timestamp: string;
}

export interface HandResult {
  winnerUserId: string;
  winnerName: string;
  handRank: string; // e.g. "Full House"
  potWon: number;
  players: {
    userId: string;
    agentName: string;
    holeCards: [Card, Card];
    handRank: string;
    chipChange: number;
  }[];
  creditDeltas?: Record<string, number>; // { userId: creditDelta, ... }
}

// ---- User Stats ----
export interface UserStats {
  userId: string;
  totalGames: number;
  totalWins: number;
  totalEarnings: number;
  biggestPot: number;
  favoriteAgent: string;
}
