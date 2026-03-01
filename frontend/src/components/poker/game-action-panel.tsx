"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Send, MessageSquare, AlertCircle } from "lucide-react";
import type { PlayerState } from "@/types";
import { useGameStore } from "@/stores/game-store";
import { useUserStore } from "@/stores/user-store";

interface GameActionPanelProps {
  currentPlayer: PlayerState | null;
  onAgentPrompt?: (prompt: string) => void;
}

export function GameActionPanel({
  currentPlayer,
  onAgentPrompt,
}: GameActionPanelProps) {
  const [agentPrompt, setAgentPrompt] = useState("");
  const chargeForPrompt = useGameStore((s) => s.chargeForPrompt);
  const getPromptCost = useGameStore((s) => s.getPromptCost);
  const credits = useUserStore((s) => s.credits);
  const fetchCredits = useUserStore((s) => s.fetchCredits);
  
  const promptCost = currentPlayer ? getPromptCost(currentPlayer.userId) : 10;
  const canAfford = credits !== null ? credits >= promptCost : false;

  const handlePromptSubmit = async () => {
    if (!agentPrompt.trim() || !currentPlayer) return;
    
    // Try to charge the player from their account credits
    const chargeSuccess = await chargeForPrompt(currentPlayer.userId);
    if (!chargeSuccess) return; // Not enough credits
    
    // Refresh credits from server to show updated balance
    await fetchCredits();
    
    // Send the prompt after successful charge
    onAgentPrompt?.(agentPrompt);
    setAgentPrompt("");
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Current player info */}
      {currentPlayer && (
        <Card className="bg-slate-900/80 border-emerald-600/30 p-3">
          <p className="text-xs text-slate-400 mb-1">Current Player</p>
          <p className="text-sm font-bold text-yellow-300">{currentPlayer.agentName}</p>
          <div className="text-xs text-slate-400 mt-1">
            💰 Credits: {credits !== null ? credits.toLocaleString() : "—"}
          </div>
        </Card>
      )}

      {/* Agent prompt intervention */}
      <Card className="bg-slate-900/80 border-purple-600/30 p-4 flex-1 flex flex-col">
        <div className="mb-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-bold text-purple-300 flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              💬 Agent Personality Prompt
            </p>
            <span className="text-xs font-semibold text-purple-400 bg-purple-900/40 px-2 py-1 rounded">
              Cost: {promptCost} 💰
            </span>
          </div>
          {!canAfford && (
            <div className="text-xs text-amber-400 flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3" />
              Not enough credits ({credits !== null ? credits : 0}/{promptCost})
            </div>
          )}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-3 flex-1 flex flex-col"
        >
          <textarea
            value={agentPrompt}
            onChange={(e) => setAgentPrompt(e.target.value)}
            placeholder="e.g., 'Play more aggressively' or 'Only bluff on weak hands'"
            className="flex-1 bg-slate-800 border border-purple-600/50 text-white placeholder-slate-400 rounded px-3 py-2 text-sm resize-none focus:border-purple-500 focus:outline-none"
          />
          <Button
            onClick={handlePromptSubmit}
            className="w-full gap-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold"
            disabled={!agentPrompt.trim() || !canAfford}
          >
            <Send className="w-4 h-4" />
            Send Prompt ({promptCost} 💰)
          </Button>
        </motion.div>
      </Card>
    </div>
  );
}