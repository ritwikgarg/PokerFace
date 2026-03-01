"use client";

import type { ActionLogEntry } from "@/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";

interface ActionLogProps {
  entries: ActionLogEntry[];
}

const actionColors: Record<string, string> = {
  fold: "text-muted-foreground",
  check: "text-green-400",
  call: "text-blue-400",
  raise: "text-orange-400",
  "all-in": "text-red-400",
};

export function ActionLog({ entries }: ActionLogProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="text-sm font-semibold px-3 py-2 border-b">Action Log</div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 max-h-[300px]">
        <AnimatePresence initial={false}>
          {entries.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              Waiting for actions...
            </p>
          ) : (
            [...entries].reverse().map((entry, i) => (
              <motion.div
                key={`${entry.timestamp}-${i}`}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 text-xs py-1 px-2 rounded bg-muted/30"
              >
                <span className="font-medium truncate max-w-[80px]">
                  {entry.playerName}
                </span>
                <span className={`font-semibold ${actionColors[entry.action] ?? ""}`}>
                  {entry.action.toUpperCase()}
                </span>
                {entry.amount !== undefined && entry.amount > 0 && (
                  <span className="text-muted-foreground font-mono">
                    ${entry.amount}
                  </span>
                )}
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
