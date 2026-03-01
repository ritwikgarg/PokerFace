/**
 * Utility for calling the Flask backend API (http://localhost:8000/api/...).
 *
 * Used by Next.js API routes to sync rooms/agents with the backend's
 * in-memory stores before/after Prisma writes.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function backendFetch<T = unknown>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BACKEND_URL}/api${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { error?: string; errors?: string[] };
    const message =
      body.error ??
      (Array.isArray(body.errors) ? body.errors.join("; ") : null) ??
      `Backend error: ${res.status}`;
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

/**
 * Sync an agent from Prisma into the Flask backend's in-memory orchestrator.
 * Uses upsert logic: creates if missing, updates if exists.
 */
export async function syncAgentToBackend(agent: {
  id: string;
  userId: string;
  name: string;
  baseLLM: string;
  playStyle: string;
  riskTolerance: number;
  deception: number;
  personalityPrompt: string;
  previousGamesHistory: number;
}): Promise<void> {
  try {
    // Try to get existing agent
    await backendFetch(`/agents/${agent.id}`);
    // Agent exists — update it
    await backendFetch(`/agents/${agent.id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: agent.name,
        baseLLM: agent.baseLLM,
        playStyle: agent.playStyle,
        riskTolerance: agent.riskTolerance,
        deception: agent.deception,
        personalityPrompt: agent.personalityPrompt,
        previousGamesHistory: agent.previousGamesHistory,
        userId: agent.userId,
      }),
    });
  } catch {
    // Agent doesn't exist — create it
    await backendFetch("/agents", {
      method: "POST",
      body: JSON.stringify({
        id: agent.id,
        name: agent.name,
        baseLLM: agent.baseLLM,
        playStyle: agent.playStyle,
        riskTolerance: agent.riskTolerance,
        deception: agent.deception,
        personalityPrompt: agent.personalityPrompt,
        previousGamesHistory: agent.previousGamesHistory,
        userId: agent.userId,
      }),
    });
  }
}
