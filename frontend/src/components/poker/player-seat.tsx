"use client";

import { motion } from "framer-motion";
import type { PlayerState } from "@/types";
import { PokerCard } from "./poker-card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Bot, Shield, Crown } from "lucide-react";

interface PlayerSeatProps {
  player: PlayerState;
  position: { x: string; y: string };
  isCurrentUser?: boolean;
}

export function PlayerSeat({
  player,
  position,
  isCurrentUser = false,
}: PlayerSeatProps) {
  const getStatusColor = () => {
    if (player.isFolded) return "bg-gray-600";
    if (player.isAllIn) return "bg-red-600";
    if (player.isActive) return "bg-yellow-500 animate-pulse";
    return "bg-emerald-700";
  };

  const getLastActionColor = () => {
    switch (player.lastAction) {
      case "fold":
        return "text-gray-400";
      case "check":
        return "text-blue-400";
      case "call":
        return "text-green-400";
      case "raise":
        return "text-red-400";
      case "all-in":
        return "text-red-500 font-bold";
      default:
        return "text-white";
    }
  };

  return (
    <motion.div
      className="absolute w-32 flex flex-col items-center gap-2"
      style={{
        left: position.x,
        top: position.y,
        transform: "translate(-50%, -50%)",
      }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      {/* Player seat card */}
      <motion.div
        className={`relative w-full px-3 py-2 rounded-lg backdrop-blur-sm shadow-lg transition-all ${
          isCurrentUser
            ? "bg-gradient-to-r from-amber-600/80 to-yellow-600/80 border-2 border-yellow-400"
            : "bg-gradient-to-r from-slate-700/80 to-slate-800/80 border border-slate-600"
        }`}
        animate={{
          boxShadow: player.isActive
            ? "0 0 20px rgba(234, 179, 8, 0.6)"
            : "none",
        }}
      >
        {/* Status indicator dot */}
        <motion.div
          className={`absolute -top-1 -right-1 w-4 h-4 rounded-full ${getStatusColor()} border-2 border-white`}
          animate={player.isActive ? { scale: [1, 1.2, 1] } : {}}
          transition={{ duration: 0.6, repeat: Infinity }}
        />

        {/* Dealer badge */}
        {player.isDealer && (
          <motion.div
            className="absolute -top-2 -left-2 bg-yellow-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shadow-lg"
            animate={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Crown className="w-3 h-3" />
          </motion.div>
        )}

        {/* Avatar and name */}
        <div className="flex items-center gap-2 mb-1.5">
          <Avatar className="w-6 h-6 border border-white">
            <AvatarImage src={player.userImage} />
            <AvatarFallback>
              <Bot className="w-3 h-3" />
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-white truncate">
              {player.agentName}
            </p>
            <p className="text-[10px] text-gray-200">Agent</p>
          </div>
        </div>

        {/* Chips display */}
        <div className="flex items-center gap-1 text-xs text-yellow-300 font-semibold mb-1">
          <Shield className="w-3 h-3" />
          ${player.chips}
        </div>

        {/* Current bet */}
        {player.currentBet > 0 && (
          <motion.div
            className="text-xs text-orange-300 font-bold mb-1"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200 }}
          >
            Bet: ${player.currentBet}
          </motion.div>
        )}

        {/* Last action label */}
        {player.lastAction && (
          <motion.div
            className={`text-xs font-semibold ${getLastActionColor()} capitalize`}
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
          >
            {player.lastAction === "all-in" ? "🔥 All In!" : player.lastAction}
          </motion.div>
        )}

        {/* Thinking indicator */}
        {player.isThinking && (
          <motion.div
            className="text-xs text-purple-400 font-semibold flex items-center gap-1"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
          >
            💭 Thinking...
            <motion.div
              className="flex gap-0.5"
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1.4, repeat: Infinity }}
            >
              <span>.</span>
              <span style={{ animationDelay: "0.2s" }}>.</span>
              <span style={{ animationDelay: "0.4s" }}>.</span>
            </motion.div>
          </motion.div>
        )}

        {/* Folded indicator */}
        {player.isFolded && (
          <motion.div
            className="text-xs font-bold text-gray-300 italic"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            Folded
          </motion.div>
        )}
      </motion.div>

      {/* Hole cards (visible for current user) */}
      {isCurrentUser && player.holeCards && !player.isFolded && (
        <motion.div
          className="flex gap-0 -mt-6"
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <PokerCard
            card={player.holeCards[0]}
            faceUp={true}
            size="sm"
            delay={0}
          />
          <PokerCard
            card={player.holeCards[1]}
            faceUp={true}
            size="sm"
            delay={0.1}
          />
        </motion.div>
      )}

      {/* Hidden cards (for other players) */}
      {!isCurrentUser && player.holeCards && !player.isFolded && (
        <motion.div
          className="flex gap-1"
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <PokerCard card={null} faceUp={false} size="sm" delay={0} />
          <PokerCard card={null} faceUp={false} size="sm" delay={0.1} />
        </motion.div>
      )}
    </motion.div>
  );
}
