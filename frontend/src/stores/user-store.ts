import { create } from "zustand";
import type { AgentConfig } from "@/types";

interface UserStore {
  selectedAgentId: string | null;
  agents: AgentConfig[];
  credits: number | null;
  isLoading: boolean;
  setSelectedAgentId: (id: string | null) => void;
  setAgents: (agents: AgentConfig[]) => void;
  setCredits: (credits: number) => void;
  fetchCredits: () => Promise<void>;
  fetchAgents: () => Promise<void>;
  addAgent: (agent: AgentConfig) => void;
  createAgent: (data: Omit<AgentConfig, "id" | "userId" | "createdAt" | "updatedAt">) => Promise<AgentConfig>;
  updateAgentRemote: (id: string, data: Omit<AgentConfig, "id" | "userId" | "createdAt" | "updatedAt">) => Promise<AgentConfig>;
  deleteAgent: (id: string) => Promise<void>;
  updateAgent: (id: string, updates: Partial<AgentConfig>) => void;
  removeAgent: (id: string) => void;
}

export const useUserStore = create<UserStore>((set, get) => ({
  selectedAgentId: null,
  agents: [],
  credits: null,
  isLoading: false,
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
  setAgents: (agents) => set({ agents }),
  setCredits: (credits) => set({ credits }),

  fetchCredits: async () => {
    try {
      const res = await fetch("/api/credits");
      if (!res.ok) return;
      const data = await res.json();
      set({ credits: data.credits });
    } catch {
      // ignore
    }
  },

  fetchAgents: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch("/api/agents");
      if (!res.ok) throw new Error("Failed to fetch agents");
      const agents = await res.json();
      set({ agents });
    } finally {
      set({ isLoading: false });
    }
  },

  createAgent: async (data) => {
    const res = await fetch("/api/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error ?? "Failed to create agent");
    }
    const agent = await res.json();
    set((state) => ({ agents: [agent, ...state.agents] }));
    // Refresh credits after spending
    get().fetchCredits();
    return agent;
  },

  updateAgentRemote: async (id, data) => {
    const res = await fetch(`/api/agents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error ?? "Failed to update agent");
    }
    const updated = await res.json();
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? updated : a)),
    }));
    // Refresh credits after update
    get().fetchCredits();
    return updated;
  },

  deleteAgent: async (id) => {
    const res = await fetch(`/api/agents/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error ?? "Failed to delete agent");
    }
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== id),
      selectedAgentId: state.selectedAgentId === id ? null : state.selectedAgentId,
    }));
    // Refresh credits after refund
    get().fetchCredits();
  },

  // Local-only helpers (kept for backward compat)
  addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent] })),
  updateAgent: (id, updates) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...updates } : a)),
    })),
  removeAgent: (id) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== id),
      selectedAgentId: state.selectedAgentId === id ? null : state.selectedAgentId,
    })),
}));
