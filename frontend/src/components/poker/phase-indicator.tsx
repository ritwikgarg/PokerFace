"use client";

import type { GamePhase } from "@/types";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";

interface PhaseIndicatorProps {
  phase: GamePhase;
  handNumber: number;
}

const phaseConfig: Record<GamePhase, { label: string; color: string }> = {
  "pre-flop": { label: "Pre-Flop", color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  flop: { label: "Flop", color: "bg-green-500/20 text-green-400 border-green-500/30" },
  turn: { label: "Turn", color: "bg-orange-500/20 text-orange-400 border-orange-500/30" },
  river: { label: "River", color: "bg-red-500/20 text-red-400 border-red-500/30" },
  showdown: { label: "Showdown", color: "bg-purple-500/20 text-purple-400 border-purple-500/30" },
};

const phases: GamePhase[] = ["pre-flop", "flop", "turn", "river", "showdown"];

export function PhaseIndicator({ phase, handNumber }: PhaseIndicatorProps) {
  const currentIndex = phases.indexOf(phase);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="text-xs text-muted-foreground">Hand #{handNumber}</div>
      <div className="flex items-center gap-1">
        {phases.map((p, i) => {
          const config = phaseConfig[p];
          const isActive = p === phase;
          const isPast = i < currentIndex;

          return (
            <div key={p} className="flex items-center">
              <motion.div
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium border transition-all ${
                  isActive
                    ? config.color
                    : isPast
                    ? "bg-muted text-muted-foreground border-muted"
                    : "bg-background text-muted-foreground/50 border-border"
                }`}
                animate={isActive ? { scale: [1, 1.05, 1] } : {}}
                transition={{ duration: 1, repeat: isActive ? Infinity : 0 }}
              >
                {config.label}
              </motion.div>
              {i < phases.length - 1 && (
                <div
                  className={`w-3 h-0.5 ${
                    isPast ? "bg-muted-foreground/50" : "bg-border"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
