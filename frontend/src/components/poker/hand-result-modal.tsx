"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { HandResult } from "@/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { PokerCard } from "./poker-card";
import { Trophy } from "lucide-react";

interface HandResultModalProps {
  result: HandResult | null;
  open: boolean;
  onClose: () => void;
  onNextHand?: () => void;
}

export function HandResultModal({ result, open, onClose, onNextHand }: HandResultModalProps) {
  if (!result) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="text-center">
          <DialogTitle className="flex items-center justify-center gap-2 text-xl">
            <Trophy className="h-6 w-6 text-yellow-500" />
            Hand Result
          </DialogTitle>
          <DialogDescription>
            {result.winnerName} wins with {result.handRank}!
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Winner highlight */}
          <motion.div
            className="flex flex-col items-center gap-2 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <span className="text-sm text-muted-foreground">Winner</span>
            <span className="text-lg font-bold">{result.winnerName}</span>
            <span className="text-sm text-yellow-400">{result.handRank}</span>
            <span className="text-2xl font-mono font-bold text-green-400">
              +${result.potWon.toLocaleString()}
            </span>
          </motion.div>

          {/* All players */}
          <div className="space-y-2">
            {result.players.map((p, i) => (
              <motion.div
                key={p.userId}
                className="flex items-center gap-3 p-2 rounded-lg bg-muted/30"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.3 + i * 0.1 }}
              >
                <span className="text-sm font-medium w-24 truncate">
                  {p.agentName}
                </span>
                <div className="flex gap-1">
                  <PokerCard card={p.holeCards[0]} faceUp size="sm" />
                  <PokerCard card={p.holeCards[1]} faceUp size="sm" delay={0.05} />
                </div>
                <span
                  className={`ml-auto text-sm font-mono font-bold ${
                    p.chipChange >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {p.chipChange >= 0 ? "+" : ""}${p.chipChange.toLocaleString()}
                </span>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="flex gap-3">
          {onNextHand && (
            <Button className="flex-1" onClick={onNextHand}>
              Next Hand
            </Button>
          )}
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
