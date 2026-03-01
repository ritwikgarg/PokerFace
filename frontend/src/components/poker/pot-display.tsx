"use client";

import { motion } from "framer-motion";

interface PotDisplayProps {
  amount: number;
}

export function PotDisplay({ amount }: PotDisplayProps) {
  return (
    <motion.div
      className="flex flex-col items-center gap-3"
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ type: "spring", stiffness: 200 }}
    >
      <motion.div
        className="relative text-center"
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 1, repeat: Infinity }}
      >
        <div className="text-emerald-300 text-xs font-semibold uppercase tracking-widest">
          💰 Pot 💰
        </div>
        <div className="text-5xl font-black text-yellow-400 drop-shadow-xl mt-1">
          ${amount.toLocaleString()}
        </div>
      </motion.div>
    </motion.div>
  );
}
