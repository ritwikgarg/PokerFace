import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAuthUserId, unauthorized, badRequest } from "@/lib/api-helpers";
import { ROOM_CODE_LENGTH, MAX_PLAYERS, STARTING_CHIPS } from "@/lib/constants";
import { backendFetch, syncAgentToBackend } from "@/lib/backend";

function generateRoomCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < ROOM_CODE_LENGTH; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

// POST /api/rooms — create a new room
export async function POST(request: Request) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const body = await request.json();
  const { agentId } = body as { agentId?: string };

  if (!agentId) return badRequest("agentId is required");

  // Verify the agent belongs to this user
  const agent = await prisma.agent.findFirst({
    where: { id: agentId, userId },
  });
  if (!agent) return badRequest("Agent not found");

  // Get user info for the backend
  const user = await prisma.user.findUnique({ where: { id: userId } });

  // Sync agent to Flask backend's in-memory orchestrator
  await syncAgentToBackend({
    id: agent.id,
    userId: agent.userId,
    name: agent.name,
    baseLLM: agent.baseLLM,
    playStyle: agent.playStyle,
    riskTolerance: agent.riskTolerance,
    deception: agent.deception,
    personalityPrompt: agent.personalityPrompt,
    previousGamesHistory: agent.previousGamesHistory,
  });

  // Create room in Flask backend (generates the code there)
  const backendRoom = await backendFetch<{ code: string; room: Record<string, unknown> }>("/rooms", {
    method: "POST",
    body: JSON.stringify({
      agentId: agent.id,
      userId,
      userName: user?.name ?? "Host",
      userImage: user?.image,
    }),
  });

  const code = backendRoom.code;

  // Also persist in Prisma for historical tracking
  try {
    await prisma.room.create({
      data: {
        code,
        hostId: userId,
        players: {
          create: {
            userId,
            agentId,
            seat: 0,
            chips: STARTING_CHIPS,
            ready: true,
          },
        },
      },
    });
  } catch {
    // Prisma write is best-effort — backend is the source of truth for live rooms
  }

  return NextResponse.json({ code, room: backendRoom.room }, { status: 201 });
}
