"use client";

import { useEffect, useRef, useCallback } from "react";
import { getSocket, connectSocket, disconnectSocket } from "@/lib/socket";
import { useGameStore } from "@/stores/game-store";
import type { GameState, Card, PlayerAction, HandResult, Room } from "@/types";

interface UseGameSocketOptions {
  roomCode: string | null;
  userId: string | null;
  /** Called whenever the lobby room state changes (player joined/left/ready) */
  onRoomUpdated?: (room: Room) => void;
}

export function useGameSocket({ roomCode, userId, onRoomUpdated }: UseGameSocketOptions) {
  const socketRef = useRef(getSocket());
  const {
    setGameState,
    setPhase,
    setCommunityCards,
    setPot,
    updatePlayer,
    setActivePlayer,
    setPlayerThinking,
    addActionLog,
    playerAction,
    setHandResult,
    setConnected,
    resetHand,
    applyCreditDeltas,
  } = useGameStore();

  // Keep callback ref stable
  const onRoomUpdatedRef = useRef(onRoomUpdated);
  onRoomUpdatedRef.current = onRoomUpdated;

  useEffect(() => {
    if (!roomCode || !userId) return;

    const socket = connectSocket();
    socketRef.current = socket;

    socket.on("connect", () => {
      console.log("✅ Socket connected");
      setConnected(true);
      socket.emit("join-room", { roomCode, userId });
    });

    socket.on("disconnect", () => {
      setConnected(false);
    });

    // ── Lobby events ─────────────────────────────────────────────

    socket.on("room-updated", (room: Room) => {
      onRoomUpdatedRef.current?.(room);
    });

    // ── Game events ──────────────────────────────────────────────

    // Full game state snapshot (on game start or reconnect)
    socket.on("game-started", (state: GameState) => {
      console.log("🎮 Game started:", state);
      setGameState(state);
    });

    socket.on("game-state", (state: GameState) => {
      console.log("📊 Game state updated:", state);
      setGameState(state);
    });

    // Cards dealt to players
    socket.on("cards-dealt", (data: { seatIndex: number; cards: [Card, Card] }) => {
      console.log("🃏 Cards dealt:", data);
      updatePlayer(data.seatIndex, { holeCards: data.cards });
    });

    // Player took an action
    socket.on(
      "game:player_acted",
      (data: { seatIndex: number; action: PlayerAction; amount?: number; pot: number; nextActive: number; playerName?: string }) => {
        playerAction(data.seatIndex, data.action, data.amount);
        setPot(data.pot);
        setActivePlayer(data.nextActive);
        addActionLog({
          playerName: data.playerName ?? "",
          action: data.action,
          amount: data.amount,
          timestamp: new Date().toISOString(),
        });
      }
    );

    // Player is thinking (before they take an action)
    socket.on("game:player_thinking", (data: { seatIndex: number; player_id: string }) => {
      console.log("💭 Player thinking:", data);
      setPlayerThinking(data.seatIndex);
    });

    // Phase changed
    socket.on("game:phase_changed", (data: { phase: GameState["phase"] }) => {
      console.log("📍 Phase changed:", data);
      setPhase(data.phase);
    });

    // Community cards revealed (flop/turn/river)
    socket.on("game:community_cards_revealed", (data: { phase: GameState["phase"]; cards: Card[] }) => {
      console.log("🌊 Community cards revealed:", data);
      setPhase(data.phase);
      setCommunityCards(data.cards);
    });

    // Full state sync (for recovery)
    socket.on("game:full_state_sync", (state: GameState) => {
      console.log("🔄 Full state sync:", state);
      setGameState(state);
    });

    // Hand result with chip changes
    socket.on("game:hand_result", (result: HandResult) => {
      console.log("🏆 Hand result:", result);
      setPhase("showdown");
      setHandResult(result);
      
      // Update credits if credit deltas are provided
      if (result.creditDeltas) {
        applyCreditDeltas(result.creditDeltas);
      }
    });

    // Legacy: Showdown (fallback)
    socket.on("showdown", (result: HandResult) => {
      console.log("🏆 Showdown:", result);
      setPhase("showdown");
      setHandResult(result);
    });

    // New round
    socket.on("round-end", () => {
      console.log("🔄 Round ended, resetting...");
      // Give time for result modal, then reset
      setTimeout(() => {
        resetHand();
      }, 5000);
    });

    // Error from backend
    socket.on("error", (data: { message: string }) => {
      console.error("[Socket] Error from server:", data.message);
    });

    return () => {
      socket.emit("leave-room", { roomCode });
      socket.off("connect");
      socket.off("disconnect");
      socket.off("room-updated");
      socket.off("game-started");
      socket.off("game-state");
      socket.off("cards-dealt");
      socket.off("game:player_acted");
      socket.off("game:player_thinking");
      socket.off("game:phase_changed");
      socket.off("game:community_cards_revealed");
      socket.off("game:full_state_sync");
      socket.off("game:hand_result");
      socket.off("showdown");
      socket.off("round-end");
      socket.off("error");
      disconnectSocket();
    };
  }, [roomCode, userId]);

  // ── Actions the UI can emit ────────────────────────────────────

  const emitToggleReady = useCallback(() => {
    if (!roomCode || !userId) return;
    socketRef.current.emit("toggle-ready", { roomCode, userId });
  }, [roomCode, userId]);

  const emitStartGame = useCallback(() => {
    if (!roomCode || !userId) return;
    socketRef.current.emit("start-game", { roomCode, userId });
  }, [roomCode, userId]);

  const emitPlayerAction = useCallback(
    (action: string, amount?: number) => {
      if (!roomCode) return;
      socketRef.current.emit("player-action", {
        roomCode,
        action,
        amount,
      });
    },
    [roomCode]
  );

  return {
    socket: socketRef.current,
    emitToggleReady,
    emitStartGame,
    emitPlayerAction,
  };
}