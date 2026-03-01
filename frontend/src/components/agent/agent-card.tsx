"use client";

import type { AgentConfig } from "@/types";
import { LLM_MODELS, PLAY_STYLES } from "@/lib/constants";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Bot, Flame, Sparkles, Brain, Pencil, Trash2 } from "lucide-react";

interface AgentCardProps {
  agent: AgentConfig;
  onSelect?: (agent: AgentConfig) => void;
  onEdit?: (agent: AgentConfig) => void;
  onDelete?: (agent: AgentConfig) => void;
  selected?: boolean;
  compact?: boolean;
}

export function AgentCard({
  agent,
  onSelect,
  onEdit,
  onDelete,
  selected = false,
  compact = false,
}: AgentCardProps) {
  const llmLabel = LLM_MODELS.find((m) => m.value === agent.baseLLM)?.label ?? agent.baseLLM;
  const styleLabel =
    PLAY_STYLES.find((s) => s.value === agent.playStyle)?.label ?? agent.playStyle;

  return (
    <Card
      className={`transition-all cursor-pointer hover:shadow-md ${
        selected ? "ring-2 ring-primary border-primary" : ""
      } ${onSelect ? "hover:border-primary/50" : ""}`}
      onClick={() => onSelect?.(agent)}
    >
      <CardHeader className={compact ? "pb-2" : undefined}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{agent.name}</CardTitle>
              <CardDescription className="text-xs">{llmLabel}</CardDescription>
            </div>
          </div>
          <div className="flex gap-1">
            {onEdit && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(agent);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(agent);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className={compact ? "pt-0" : undefined}>
        <div className="flex flex-wrap gap-2 mb-3">
          <Badge variant="secondary" className="text-xs">
            {styleLabel}
          </Badge>
        </div>
        {!compact && (
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div className="flex items-center gap-1.5">
              <Flame className="h-3.5 w-3.5 text-orange-500" />
              <div>
                <div className="text-muted-foreground text-xs">Risk</div>
                <div className="font-medium">{agent.riskTolerance}%</div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-purple-500" />
              <div>
                <div className="text-muted-foreground text-xs">Bluff</div>
                <div className="font-medium">{agent.deception}%</div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <img src="/image.png" alt="History" className="h-3.5 w-3.5 rounded-sm object-contain" />
              <div>
                <div className="text-muted-foreground text-xs">History</div>
                <div className="font-medium">{agent.previousGamesHistory === 0 ? "Off" : `Lv.${agent.previousGamesHistory}`}</div>
              </div>
            </div>
          </div>
        )}
        {agent.personalityPrompt && !compact && (
          <p className="mt-3 text-xs text-muted-foreground line-clamp-2 italic">
            &ldquo;{agent.personalityPrompt}&rdquo;
          </p>
        )}
      </CardContent>
    </Card>
  );
}
