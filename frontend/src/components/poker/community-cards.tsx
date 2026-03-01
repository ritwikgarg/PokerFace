"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Card } from "@/types";
import { PokerCard } from "./poker-card";

interface CommunityCardsProps {
  cards: Card[];
}

export function CommunityCards({ cards }: CommunityCardsProps) {
  const slots = Array.from({ length: 5 }, (_, i) => cards[i] ?? null);

  return (
    <div className="flex gap-3 justify-center items-center">
      <AnimatePresence mode="wait">
        {slots.map((card, index) => (
          <motion.div
            key={`community-${index}`}
            initial={{ scale: 0, rotateY: 180, y: -20 }}
            animate={{ scale: 1, rotateY: 0, y: 0 }}
            exit={{ scale: 0, rotateY: 180, y: -20 }}
            transition={{ duration: 0.4, delay: index * 0.12 }}
          >
            {card ? (
              <PokerCard card={card} faceUp={true} size="md" delay={0} />
            ) : (
              <motion.div
                className="w-16 h-24 rounded-lg border-2 border-dashed border-emerald-400/30 flex items-center justify-center bg-emerald-900/20"
                animate={{ opacity: [0.5, 0.8, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <div className="text-emerald-400/20 text-xs font-semibold">—</div>
              </motion.div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
