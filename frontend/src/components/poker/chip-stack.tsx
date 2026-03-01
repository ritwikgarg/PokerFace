"use client";

import { motion } from "framer-motion";

interface ChipStackProps {
  amount: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const chipColors = [
  "bg-red-500",     // 1s
  "bg-blue-500",    // 5s
  "bg-green-500",   // 25s
  "bg-black",       // 100s
  "bg-purple-600",  // 500s
];

export function ChipStack({ amount, size = "md", className = "" }: ChipStackProps) {
  if (amount <= 0) return null;

  // Determine chip breakdown (visual only)
  const chipCount = Math.min(Math.ceil(amount / 50), 8);
  const chipSize = size === "sm" ? "w-5 h-5" : size === "lg" ? "w-8 h-8" : "w-6 h-6";

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* Chip stack visual */}
      <div className="relative" style={{ height: chipCount * 3 + 20 }}>
        {Array.from({ length: chipCount }).map((_, i) => (
          <motion.div
            key={i}
            className={`${chipSize} rounded-full absolute border-2 border-white/30 shadow-sm ${
              chipColors[i % chipColors.length]
            }`}
            style={{ bottom: i * 3 }}
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: i * 0.05 }}
          />
        ))}
      </div>
      {/* Amount label */}
      <span
        className={`font-mono font-bold mt-1 ${
          size === "sm" ? "text-xs" : size === "lg" ? "text-base" : "text-sm"
        }`}
      >
        ${amount.toLocaleString()}
      </span>
    </div>
  );
}
