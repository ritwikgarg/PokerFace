import { create } from "zustand";
import type {
  GameState,
  GamePhase,
  PlayerState,
  Card,
  ActionLogEntry,
  HandResult,
  PlayerAction,
} from "@/types";

interface GameStore {
  // State
  gameState: GameState | null;
  handResult: HandResult | null;
  isConnected: boolean;

  // Setters
  setGameState: (state: GameState) => void;
  setHandResult: (result: HandResult | null) => void;
  setConnected: (connected: boolean) => void;

  // Granular updates (called from socket events)
  setPhase: (phase: GamePhase) => void;
  setCommunityCards: (cards: Card[]) => void;
  setPot: (pot: number) => void;
  updatePlayer: (seatIndex: number, updates: Partial<PlayerState>) => void;
  setActivePlayer: (seatIndex: number) => void;
  setPlayerThinking: (seatIndex: number) => void;
  addActionLog: (entry: ActionLogEntry) => void;
  playerAction: (seatIndex: number, action: PlayerAction, amount?: number) => void;
  resetHand: () => void;
  chargeForPrompt: (userId: string) => Promise<boolean>; // Now async - returns true if charge was successful
  getPromptCost: (userId: string) => number; // Get current cost for a player
  applyCreditDeltas: (creditDeltas: Record<string, number>) => Promise<void>; // Update credits from hand result
}

export const useGameStore = create<GameStore>((set) => ({
  gameState: null,
  handResult: null,
  isConnected: false,

  setGameState: (gameState) => set({ gameState }),
  setHandResult: (handResult) => set({ handResult }),
  setConnected: (isConnected) => set({ isConnected }),

  setPhase: (phase) =>
    set((state) => {
      if (!state.gameState) return state;
      return { gameState: { ...state.gameState, phase } };
    }),

  setCommunityCards: (cards) =>
    set((state) => {
      if (!state.gameState) return state;
      return { gameState: { ...state.gameState, communityCards: cards } };
    }),

  setPot: (pot) =>
    set((state) => {
      if (!state.gameState) return state;
      return { gameState: { ...state.gameState, pot } };
    }),

  updatePlayer: (seatIndex, updates) =>
    set((state) => {
      if (!state.gameState) return state;
      const players = state.gameState.players.map((p) =>
        p.seatIndex === seatIndex ? { ...p, ...updates } : p
      );
      return { gameState: { ...state.gameState, players } };
    }),

  setActivePlayer: (seatIndex) =>
    set((state) => {
      if (!state.gameState) return state;
      const players = state.gameState.players.map((p) => ({
        ...p,
        isActive: p.seatIndex === seatIndex,
      }));
      return {
        gameState: { ...state.gameState, players, activePlayerIndex: seatIndex },
      };
    }),

  setPlayerThinking: (seatIndex) =>
    set((state) => {
      if (!state.gameState) return state;
      const players = state.gameState.players.map((p) =>
        p.seatIndex === seatIndex ? { ...p, isThinking: true } : { ...p, isThinking: false }
      );
      return { gameState: { ...state.gameState, players } };
    }),

  addActionLog: (entry) =>
    set((state) => {
      if (!state.gameState) return state;
      return {
        gameState: {
          ...state.gameState,
          actionLog: [...state.gameState.actionLog, entry],
        },
      };
    }),

  playerAction: (seatIndex, action, amount) =>
    set((state) => {
      if (!state.gameState) return state;
      const players = state.gameState.players.map((p) => {
        if (p.seatIndex !== seatIndex) return p;
        switch (action) {
          case "fold":
            return { ...p, isFolded: true, isActive: false, lastAction: action };
          case "all-in":
            return {
              ...p,
              isAllIn: true,
              currentBet: p.chips + p.currentBet,
              chips: 0,
              lastAction: action,
            };
          default:
            return {
              ...p,
              currentBet: amount ?? p.currentBet,
              chips: p.chips - (amount ?? 0) + p.currentBet,
              lastAction: action,
            };
        }
      });
      return { gameState: { ...state.gameState, players } };
    }),

  resetHand: () =>
    set((state) => {
      if (!state.gameState) return state;
      const players = state.gameState.players.map((p) => ({
        ...p,
        currentBet: 0,
        holeCards: null as [Card, Card] | null,
        isFolded: false,
        isAllIn: false,
        isActive: false,
        isThinking: false,
        lastAction: null,
      }));
      return {
        gameState: {
          ...state.gameState,
          phase: "pre-flop" as GamePhase,
          communityCards: [],
          pot: 0,
          currentBet: 0,
          players,
          actionLog: [],
          handNumber: state.gameState.handNumber + 1,
        },
        handResult: null,
      };
    }),

  chargeForPrompt: async (userId: string): Promise<boolean> => {
    const state = useGameStore.getState();
    if (!state.gameState) return false;

    // Get current prompt cost for this user
    const promptCosts = state.gameState.promptCosts || {};
    const currentCost = promptCosts[userId] || 10; // Start at 10

    try {
      // Attempt to deduct cost from account credits
      const response = await fetch("/api/credits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delta: -currentCost }),
      });

      if (!response.ok) {
        console.error(`Failed to charge credits for prompt: ${response.statusText}`);
        return false;
      }

      // Update cost for next prompt (double it)
      const newPromptCosts = {
        ...promptCosts,
        [userId]: currentCost * 2,
      };

      useGameStore.setState({
        gameState: {
          ...state.gameState,
          promptCosts: newPromptCosts,
        },
      });

      return true; // Charge succeeded
    } catch (error) {
      console.error("Error charging for prompt:", error);
      return false;
    }
  },

  getPromptCost: (userId: string): number => {
    const state = useGameStore.getState();
    if (!state.gameState) return 10;
    const promptCosts = state.gameState.promptCosts || {};
    return promptCosts[userId] || 10;
  },

  applyCreditDeltas: async (creditDeltas: Record<string, number>) => {
    // Update credits via API for current user
    // The hook will call this with the deltas from the backend
    // We need to determine which delta applies to the current user
    // For now, we'll try to apply all deltas (the API will only allow updating current user)
    for (const [userId, delta] of Object.entries(creditDeltas)) {
      try {
        const response = await fetch("/api/credits", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ delta }),
        });
        if (!response.ok) {
          console.error(`Failed to update credits for ${userId}:`, response.statusText);
        }
      } catch (error) {
        console.error(`Error updating credits for ${userId}:`, error);
      }
    }
  },
}));
