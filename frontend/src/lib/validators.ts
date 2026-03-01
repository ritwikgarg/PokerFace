import { z } from "zod";

// ---- Agent Config Schema ----
export const agentConfigSchema = z.object({
  name: z
    .string()
    .min(2, "Agent name must be at least 2 characters")
    .max(30, "Agent name must be at most 30 characters"),
  riskTolerance: z
    .number()
    .min(0)
    .max(100),
  deception: z
    .number()
    .min(0)
    .max(100),
  personalityPrompt: z
    .string()
    .max(500, "Personality prompt must be under 500 characters"),
  baseLLM: z.string().min(1, "Please select a model"),
  playStyle: z.enum(["tight-aggressive", "loose-aggressive", "tight-passive", "loose-passive"]),
  previousGamesHistory: z
    .number()
    .min(0)
    .max(3),
});

export type AgentConfigFormValues = z.infer<typeof agentConfigSchema>;

// ---- Room Code Schema ----
export const roomCodeSchema = z.object({
  code: z
    .string()
    .length(6, "Room code must be exactly 6 characters")
    .regex(/^[A-Z0-9]+$/, "Room code must be uppercase alphanumeric"),
});

export type RoomCodeFormValues = z.infer<typeof roomCodeSchema>;
