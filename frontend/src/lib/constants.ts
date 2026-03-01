import type { LLMModel, PlayStyle } from "@/types";

// ---- LLM Model Options (fallback — real list fetched from backend /api/models/selectable) ----
export const LLM_MODELS: { value: string; label: string; description: string; cost: number }[] = [
  { value: "mistral-7b-instruct",   label: "Mistral 7B Instruct",   description: "Fast & capable 7B model (Mistral AI) — Free", cost: 0 },
  { value: "llama-3.1-8b-instruct", label: "Llama 3.1 8B Instruct", description: "Compact instruct model with 128K context (Meta)", cost: 50 },
  { value: "devstral-small-24b",    label: "Devstral Small 24B",    description: "Agentic coding model with 256K context (Mistral)", cost: 100 },
  { value: "qwen3.5-27b",          label: "Qwen 3.5 27B",          description: "Latest 27B with native reasoning (Alibaba)", cost: 200 },
];

// ---- Play Style Options ----
export const PLAY_STYLES: { value: PlayStyle; label: string; description: string }[] = [
  {
    value: "tight-aggressive",
    label: "Tight-Aggressive (TAG)",
    description: "Plays few hands, bets aggressively when in",
  },
  {
    value: "loose-aggressive",
    label: "Loose-Aggressive (LAG)",
    description: "Plays many hands, applies constant pressure",
  },
  {
    value: "tight-passive",
    label: "Tight-Passive (Rock)",
    description: "Plays few hands, rarely raises",
  },
  {
    value: "loose-passive",
    label: "Loose-Passive (Calling Station)",
    description: "Plays many hands, mostly calls",
  },
];

// ---- Default Agent Values ----
export const DEFAULT_AGENT_VALUES = {
  name: "",
  riskTolerance: 50,
  deception: 30,
  personalityPrompt: "",
  baseLLM: "mistral-7b-instruct" as LLMModel,
  playStyle: "tight-aggressive" as PlayStyle,
  previousGamesHistory: 0,
};

// ---- Credit Costs ----

/** Cost per model tier when creating/updating an agent (fallback — real costs from backend). */
export const MODEL_COSTS: Record<string, number> = {
  "mistral-7b-instruct":   0,   // base model — free
  "llama-3.1-8b-instruct": 50,
  "devstral-small-24b":    100,
  "qwen3.5-27b":           200,
};

/** Cost per previous-games-history level (0–3). Level 0 is disabled/free. */
export const HISTORY_COSTS: Record<number, number> = {
  0: 0,
  1: 25,
  2: 75,
  3: 150,
};

/** Starting credits for new users */
export const STARTING_CREDITS = 1000;

/** Calculate total credit cost for an agent configuration */
export function calcAgentCost(baseLLM: string, previousGamesHistory: number): number {
  return (MODEL_COSTS[baseLLM] ?? 0) + (HISTORY_COSTS[previousGamesHistory] ?? 0);
}

// ---- Game Constants ----
export const MAX_PLAYERS = 5;
export const STARTING_CHIPS = 1000;
export const SMALL_BLIND = 10;
export const BIG_BLIND = 20;
export const ROOM_CODE_LENGTH = 6;

// ---- API ----
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const SOCKET_URL = process.env.NEXT_PUBLIC_WS_URL ?? "http://localhost:8000";
