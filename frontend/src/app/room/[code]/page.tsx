"use client";

import { useParams } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { AuthGuard } from "@/components/auth/auth-guard";
import { Lobby } from "@/components/room/lobby";
import { PokerTable } from "@/components/poker/poker-table";
import { useGameStore } from "@/stores/game-store";
import { useGameSocket } from "@/hooks/use-game-socket";
import type { Room, RoomPlayer } from "@/types";
import { Loader2 } from "lucide-react";

export default function RoomPage() {
  const params = useParams();
  const roomCode = (params.code as string) ?? "";
  const { data: session } = useSession();
  const gameState = useGameStore((s) => s.gameState);
  const handResult = useGameStore((s) => s.handResult);
  const resetHand = useGameStore((s) => s.resetHand);
  const addActionLog = useGameStore((s) => s.addActionLog);
  const playerAction = useGameStore((s) => s.playerAction);

  const [roomStatus, setRoomStatus] = useState<"waiting" | "in-progress" | "finished">("waiting");
  const [lobbyPlayers, setLobbyPlayers] = useState<RoomPlayer[]>([]);
  const [isHost, setIsHost] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [useMockData, setUseMockData] = useState(true); // Use mock data for now

  const currentUserId = (session?.user as { id?: string })?.id ?? "";

  // Handle lobby updates from Socket.IO
  const handleRoomUpdated = useCallback(
    (room: Room) => {
      setRoomStatus(room.status);

      const players: RoomPlayer[] = room.players.map((p) => ({
        userId: p.userId,
        userName: p.userName ?? "Player",
        userImage: p.userImage ?? "",
        agentId: p.agentId,
        agentName: p.agentName ?? "",
        isReady: p.isReady,
        isHost: p.isHost,
      }));

      setLobbyPlayers(players);

      const me = room.players.find((p) => p.userId === currentUserId);
      if (me) setIsReady(me.isReady);

      setIsHost(room.createdBy === currentUserId || room.players.some((p) => p.userId === currentUserId && p.isHost));
      setLoading(false);
    },
    [currentUserId]
  );

  // Connect to Socket.IO
  const { socket, emitToggleReady, emitStartGame, emitPlayerAction } = useGameSocket({
    roomCode,
    userId: currentUserId,
    onRoomUpdated: handleRoomUpdated,
  });

  // Initial room fetch via API (for first render before socket connects)
  useEffect(() => {
    if (!roomCode || !currentUserId) return;

    const fetchRoom = async () => {
      try {
        const res = await fetch(`/api/rooms/${roomCode}`);
        if (!res.ok) return;
        const room = await res.json();
        handleRoomUpdated(room);
      } catch {
        // Socket will provide updates
      }
    };

    fetchRoom();
  }, [roomCode, currentUserId, handleRoomUpdated]);

  // When game-started event fires, the gameState in zustand will be set
  // and we switch from lobby to playing automatically
  const isPlaying = roomStatus === "in-progress" || !!gameState;

  const handleStart = () => {
    emitStartGame();
  };

  const handleReady = () => {
    emitToggleReady();
  };

  const handleNextHand = () => {
    resetHand();
  };

  // Action handlers for poker table
  const handleAction = useCallback((action: string, amount?: number) => {
    if (!gameState || !currentUserId) {
      console.error("Game state missing or user not authenticated");
      return;
    }

    // Find the seat index for the current user
    const seatIndex = gameState.players.findIndex(p => p.userId === currentUserId);
    if (seatIndex === -1) {
      console.error("Current user not found in game state");
      return;
    }

    emitPlayerAction(action, amount);
  }, [emitPlayerAction, gameState, currentUserId]);

  const handleAgentPrompt = useCallback((prompt: string) => {
    if (!socket || !currentUserId) {
      console.error("Socket not connected or user not authenticated");
      return;
    }

    socket.emit("agent-prompt", {
      roomCode,
      userId: currentUserId,
      prompt,
      timestamp: new Date().toISOString(),
    });
  }, [socket, roomCode, currentUserId]);

  const allReady = lobbyPlayers.every((p) => p.isHost || p.isReady);
  const enoughPlayers = lobbyPlayers.length >= 2;

  if (loading) {
    return (
      <AuthGuard>
        <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      {!isPlaying || !gameState ? (
        <Lobby
          roomCode={roomCode}
          players={lobbyPlayers}
          isHost={isHost}
          canStart={allReady && enoughPlayers}
          onStart={handleStart}
          onReady={handleReady}
          isReady={isReady}
        />
      ) : (
        <div className="h-[calc(100vh-4rem)] p-4">
          <PokerTable
            gameState={gameState}
            handResult={handResult}
            currentUserId={currentUserId}
            onAction={handleAction}
            onAgentPrompt={handleAgentPrompt}
            onNextHand={handleNextHand}
          />
        </div>
      )}
    </AuthGuard>
  );
}
