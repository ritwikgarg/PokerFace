"use client";

import { useState } from "react";
import type { GameState, HandResult } from "@/types";
import { PlayerSeat } from "./player-seat";
import { CommunityCards } from "./community-cards";
import { PotDisplay } from "./pot-display";
import { PhaseIndicator } from "./phase-indicator";
import { ActionLog } from "./action-log";
import { GameActionPanel } from "./game-action-panel";
import { HandResultModal } from "./hand-result-modal";
import { Card } from "@/components/ui/card";

interface PokerTableProps {
  gameState: GameState;
  handResult: HandResult | null;
  currentUserId?: string;
  onAction?: (action: string, amount?: number) => void;
  onAgentPrompt?: (prompt: string) => void;
  onNextHand?: () => void;
}

// Seat positions around an oval table (5 seats)
// positions are percentages relative to the table container
const SEAT_POSITIONS: { x: string; y: string }[] = [
  { x: "50%", y: "82%" },   // Seat 0 — bottom center (user)
  { x: "10%", y: "60%" },   // Seat 1 — left
  { x: "20%", y: "12%" },   // Seat 2 — top-left
  { x: "80%", y: "12%" },   // Seat 3 — top-right
  { x: "90%", y: "60%" },   // Seat 4 — right
];

export function PokerTable({ 
  gameState, 
  handResult, 
  currentUserId,
  onAction,
  onAgentPrompt,
  onNextHand 
}: PokerTableProps) {
  const [showResult, setShowResult] = useState(false);

  // Show result modal when hand result arrives
  const isShowdown = gameState.phase === "showdown" && handResult;

  return (
    <div className="flex gap-4 h-full">
      {/* Main table area */}
      <div className="flex-1 flex flex-col gap-3">
        {/* Phase indicator */}
        <PhaseIndicator phase={gameState.phase} handNumber={gameState.handNumber} />

        {/* Table */}
        <div className="relative flex-1 min-h-[500px]">
          {/* Table felt (oval) */}
          <div className="absolute inset-[5%] rounded-[50%] bg-gradient-to-b from-emerald-800 to-emerald-900 border-[8px] border-amber-900/80 shadow-2xl shadow-black/50">
            {/* Inner border */}
            <div className="absolute inset-3 rounded-[50%] border-2 border-emerald-600/30" />

            {/* Center content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <PotDisplay amount={gameState.pot} />
              <CommunityCards cards={gameState.communityCards} />
            </div>
          </div>

          {/* Player seats */}
          {gameState.players.map((player, i) => (
            <PlayerSeat
              key={player.userId}
              player={player}
              position={SEAT_POSITIONS[i] ?? SEAT_POSITIONS[0]}
              isCurrentUser={player.userId === currentUserId}
            />
          ))}
        </div>
      </div>

      {/* Sidebar: Action Log + Game Action Panel */}
      <div className="w-80 shrink-0 hidden lg:flex flex-col gap-3 overflow-hidden">
        {/* Action Log */}
        <Card className="flex-1 overflow-hidden">
          <ActionLog entries={gameState.actionLog} />
        </Card>

        {/* Game Action Panel */}
        {currentUserId && (
          <Card className="shrink-0 p-4">
            <GameActionPanel
              currentPlayer={gameState.players.find(p => p.userId === currentUserId) || null}
              onAgentPrompt={onAgentPrompt}
            />
          </Card>
        )}
      </div>

      {/* Hand result modal */}
      <HandResultModal
        result={handResult}
        open={!!isShowdown || showResult}
        onClose={() => setShowResult(false)}
        onNextHand={onNextHand}
      />
    </div>
  );
}
