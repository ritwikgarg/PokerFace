import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAuthUserId, unauthorized, notFound, badRequest } from "@/lib/api-helpers";
import { agentConfigSchema } from "@/lib/validators";
import { calcAgentCost } from "@/lib/constants";

interface Params {
  params: Promise<{ id: string }>;
}

// GET /api/agents/[id]
export async function GET(_request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { id } = await params;
  const agent = await prisma.agent.findFirst({
    where: { id, userId },
  });

  if (!agent) return notFound("Agent not found");
  return NextResponse.json(agent);
}

// PUT /api/agents/[id]
export async function PUT(request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { id } = await params;
  const existing = await prisma.agent.findFirst({ where: { id, userId } });
  if (!existing) return notFound("Agent not found");

  const body = await request.json();
  const parsed = agentConfigSchema.safeParse(body);
  if (!parsed.success) {
    return badRequest(parsed.error.issues[0]?.message ?? "Invalid input");
  }

  // Calculate cost difference (refund old, charge new)
  const oldCost = calcAgentCost(existing.baseLLM, existing.previousGamesHistory);
  const newCost = calcAgentCost(parsed.data.baseLLM, parsed.data.previousGamesHistory);
  const diff = newCost - oldCost; // positive = need to pay more, negative = refund

  if (diff > 0) {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { credits: true },
    });
    if (!user || user.credits < diff) {
      return badRequest(
        `Insufficient credits. This upgrade costs ${diff} more credits but you only have ${user?.credits ?? 0}.`
      );
    }
  }

  // Update agent and adjust credits in a transaction
  const updated = await prisma.$transaction(async (tx) => {
    if (diff !== 0) {
      await tx.user.update({
        where: { id: userId },
        data: { credits: { decrement: diff } },
      });
    }
    return tx.agent.update({
      where: { id },
      data: {
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

  return NextResponse.json(updated);
}

// DELETE /api/agents/[id]
export async function DELETE(_request: Request, { params }: Params) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const { id } = await params;
  const existing = await prisma.agent.findFirst({ where: { id, userId } });
  if (!existing) return notFound("Agent not found");

  // Refund the agent's credit cost
  const refund = calcAgentCost(existing.baseLLM, existing.previousGamesHistory);

  await prisma.$transaction(async (tx) => {
    if (refund > 0) {
      await tx.user.update({
        where: { id: userId },
        data: { credits: { increment: refund } },
      });
    }
    await tx.agent.delete({ where: { id } });
  });

  return NextResponse.json({ success: true });
}
