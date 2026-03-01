import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAuthUserId, unauthorized, badRequest } from "@/lib/api-helpers";
import { agentConfigSchema } from "@/lib/validators";
import { calcAgentCost } from "@/lib/constants";

// GET /api/agents — list current user's agents
export async function GET() {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const agents = await prisma.agent.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" },
  });

  return NextResponse.json(agents);
}

// POST /api/agents — create a new agent
export async function POST(request: Request) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const body = await request.json();
  const parsed = agentConfigSchema.safeParse(body);
  if (!parsed.success) {
    return badRequest(parsed.error.issues[0]?.message ?? "Invalid input");
  }

  // Calculate credit cost
  const cost = calcAgentCost(parsed.data.baseLLM, parsed.data.previousGamesHistory);

  // Check balance
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { credits: true },
  });
  if (!user || user.credits < cost) {
    return badRequest(
      `Insufficient credits. This agent costs ${cost} credits but you only have ${user?.credits ?? 0}.`
    );
  }

  // Deduct credits and create agent in a transaction
  const agent = await prisma.$transaction(async (tx) => {
    await tx.user.update({
      where: { id: userId },
      data: { credits: { decrement: cost } },
    });
    return tx.agent.create({
      data: {
        userId,
        name: parsed.data.name,
        playStyle: parsed.data.playStyle,
        riskTolerance: parsed.data.riskTolerance,
        deception: parsed.data.deception,
        personalityPrompt: parsed.data.personalityPrompt,
        baseLLM: parsed.data.baseLLM,
        previousGamesHistory: parsed.data.previousGamesHistory,
      },
    });
  });

  return NextResponse.json(agent, { status: 201 });
}
