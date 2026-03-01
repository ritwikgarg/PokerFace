"use client";

import type { AgentConfig } from "@/types";
import { AgentCard } from "@/components/agent/agent-card";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

interface AgentPresetPickerProps {
  agents: AgentConfig[];
  selectedId: string | null;
  onSelect: (agent: AgentConfig) => void;
  onCreateNew: () => void;
  onEdit?: (agent: AgentConfig) => void;
  onDelete?: (agent: AgentConfig) => void;
}

export function AgentPresetPicker({
  agents,
  selectedId,
  onSelect,
  onCreateNew,
  onEdit,
  onDelete,
}: AgentPresetPickerProps) {
  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <p className="text-muted-foreground mb-4">
          No agents configured yet. Create your first one!
        </p>
        <Button onClick={onCreateNew} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Agent
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            selected={agent.id === selectedId}
            onSelect={onSelect}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
        <button
          onClick={onCreateNew}
          className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-muted-foreground transition-colors hover:border-primary hover:text-primary min-h-[140px]"
        >
          <Plus className="h-8 w-8 mb-2" />
          <span className="text-sm font-medium">New Agent</span>
        </button>
      </div>
    </div>
  );
}
