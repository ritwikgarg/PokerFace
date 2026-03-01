"use client";

import { motion } from "framer-motion";
import type { Card as CardType } from "@/types";

interface PokerCardProps {
  card: CardType | null;
  faceUp?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
  delay?: number;
}

const suitSymbols: Record<string, string> = {
  hearts: "♥",
  diamonds: "♦",
  clubs: "♣",
  spades: "♠",
};

const suitColors: Record<string, string> = {
  hearts: "text-red-600",
  diamonds: "text-red-600",
  clubs: "text-black",
  spades: "text-black",
};

const sizeClasses = {
  sm: "w-12 h-16",
  md: "w-16 h-24",
  lg: "w-20 h-32",
};

export function PokerCard({
  card,
  faceUp = true,
  size = "md",
  className = "",
  delay = 0,
}: PokerCardProps) {
  const shouldShowFace = card && faceUp;

  return (
    <motion.div
      className={`${sizeClasses[size]} ${className}`}
      initial={{ rotateY: 180, opacity: 0 }}
      animate={{ rotateY: shouldShowFace ? 0 : 180, opacity: 1 }}
      transition={{ duration: 0.5, delay }}
      style={{ perspective: 1000 }}
    >
      <div className="relative w-full h-full">
        {/* Front (face up) */}
        <div
          className={`absolute inset-0 w-full h-full rounded-lg border-2 border-gray-300 shadow-lg bg-white flex flex-col items-center justify-center p-1 ${
            shouldShowFace ? "visible" : "hidden"
          }`}
        >
          {card && (
            <>
              <div className={`text-sm font-bold ${suitColors[card.suit]}`}>
                {card.rank}
              </div>
              <div className={`text-lg leading-none ${suitColors[card.suit]}`}>
                {suitSymbols[card.suit]}
              </div>
              <div className={`text-sm font-bold ${suitColors[card.suit]}`}>
                {card.rank}
              </div>
            </>
          )}
        </div>

        {/* Back (face down) */}
        <div
          className={`absolute inset-0 w-full h-full rounded-lg bg-gradient-to-br from-blue-700 to-blue-900 border-2 border-blue-600 flex items-center justify-center ${
            !shouldShowFace ? "visible" : "hidden"
          }`}
        >
          <div className="text-white text-2xl opacity-30">🂠</div>
        </div>
      </div>
    </motion.div>
  );
}
