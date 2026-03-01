import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAuthUserId, unauthorized, notFound, badRequest } from "@/lib/api-helpers";
import { STARTING_CHIPS, MAX_PLAYERS } from "@/lib/constants";
import { backendFetch, syncAgentToBackend } from "@/lib/backend";

interface Params {
  params: Promise<{ code: string }>;
}

// GET /api/rooms/[code] — get room details (from Flask backend, source of truth)
export async function GET(_request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { code } = await params;

  try {
    // Try Flask backend first (live room data)
    const room = await backendFetch<Record<string, unknown>>(`/rooms/${code}`);
    return NextResponse.json(room);
  } catch {
    // Fall back to Prisma (historical data)
    const room = await prisma.room.findUnique({
      where: { code },
      include: {
        host: { select: { id: true, name: true, image: true } },
        players: {
          include: {
            user: { select: { id: true, name: true, image: true } },
          },
          orderBy: { seat: "asc" },
        },
      },
    });

    if (!room) return notFound("Room not found");
    return NextResponse.json(room);
  }
}

// POST /api/rooms/[code]/join — join a room
export async function POST(request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { code } = await params;
  const body = await request.json();
  const { agentId } = body as { agentId?: string };
  if (!agentId) return badRequest("agentId is required");

  // Verify agent belongs to user
  const agent = await prisma.agent.findFirst({
    where: { id: agentId, userId },
  });
  if (!agent) return badRequest("Agent not found");

  // Get user info
  const user = await prisma.user.findUnique({ where: { id: userId } });

  // Sync agent to Flask backend
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

  // Ensure room exists in Flask backend (it may have been lost on backend restart)
  try {
    await backendFetch(`/rooms/${code}`);
  } catch {
    // Room not in backend memory — look it up in Prisma and re-create it
    const prismaRoom = await prisma.room.findUnique({
      where: { code },
      include: {
        host: { select: { id: true, name: true, image: true } },
        players: {
          include: {
            user: { select: { id: true, name: true, image: true } },
          },
          orderBy: { seat: "asc" },
        },
      },
    });

    if (!prismaRoom) return notFound("Room not found in database");

    // Find the host player's agentId from the players list
    const hostPlayer = prismaRoom.players.find((p) => p.userId === prismaRoom.hostId);
    const hostAgentId = hostPlayer?.agentId ?? agent.id;

    // Look up the host's agent from the Agent table and sync it
    const hostAgent = await prisma.agent.findUnique({ where: { id: hostAgentId } });
    if (hostAgent) {
      await syncAgentToBackend({
        id: hostAgent.id,
        userId: hostAgent.userId,
        name: hostAgent.name,
        baseLLM: hostAgent.baseLLM,
        playStyle: hostAgent.playStyle,
        riskTolerance: hostAgent.riskTolerance,
        deception: hostAgent.deception,
        personalityPrompt: hostAgent.personalityPrompt,
        previousGamesHistory: hostAgent.previousGamesHistory,
      });
    }

    // Re-create room in Flask backend with the same code
    await backendFetch("/rooms", {
      method: "POST",
      body: JSON.stringify({
        code,
        agentId: hostAgentId,
        userId: prismaRoom.hostId,
        userName: prismaRoom.host?.name ?? "Host",
        userImage: prismaRoom.host?.image,
      }),
    });
  }

  // Join room in Flask backend
  const result = await backendFetch<{ room: Record<string, unknown> }>(`/rooms/${code}/join`, {
    method: "POST",
    body: JSON.stringify({
      agentId: agent.id,
      userId,
      userName: user?.name ?? "Player",
      userImage: user?.image,
    }),
  });

  // Also persist join in Prisma (best-effort)
  try {
    const prismaRoom = await prisma.room.findUnique({
      where: { code },
      include: { players: true },
    });

    if (prismaRoom) {
      const alreadyJoined = prismaRoom.players.find((p) => p.userId === userId);
      if (!alreadyJoined) {
        const takenSeats = new Set(prismaRoom.players.map((p) => p.seat));
        let nextSeat = 0;
        while (takenSeats.has(nextSeat)) nextSeat++;

        await prisma.roomPlayer.create({
          data: {
            userId,
            agentId,
            roomId: prismaRoom.id,
            seat: nextSeat,
            chips: STARTING_CHIPS,
          },
        });
      }
    }
  } catch {
    // Prisma write is best-effort
  }

  return NextResponse.json(result.room);
}

// PATCH /api/rooms/[code] — update room (ready status, start game)
// NOTE: Ready and Start are now handled via Socket.IO events (toggle-ready, start-game).
// This endpoint is kept for backward compatibility but proxies to the Flask backend.
export async function PATCH(request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { code } = await params;
  const body = await request.json();
  const { action } = body as { action: "ready" | "unready" | "start" };

  if (action === "ready" || action === "unready") {
    try {
      const result = await backendFetch<{ room: Record<string, unknown> }>(`/rooms/${code}/ready`, {
        method: "POST",
        body: JSON.stringify({
          userId,
          ready: action === "ready",
        }),
      });
      return NextResponse.json(result.room);
    } catch (e) {
      return badRequest((e as Error).message);
    }
  }

  if (action === "start") {
    // Game start is handled via Socket.IO "start-game" event.
    // This REST endpoint just updates Prisma status for persistence.
    try {
      await prisma.room.update({
        where: { code },
        data: { status: "playing" },
      });
    } catch {
      // best-effort
    }
    return NextResponse.json({ message: "Use socket event 'start-game' to start the game." });
  }

  return badRequest("Invalid action");
}
