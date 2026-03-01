import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAuthUserId, unauthorized } from "@/lib/api-helpers";

// GET /api/credits — return the current user's credit balance
export async function GET() {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { credits: true },
  });

  return NextResponse.json({ credits: user?.credits ?? 0 });
}

// POST /api/credits — update the current user's credits by delta amount
export async function POST(request: Request) {
  const userId = await getAuthUserId();
  if (!userId) return unauthorized();

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { delta } = body;
  if (typeof delta !== "number") {
    return NextResponse.json(
      { error: "delta must be a number" },
      { status: 400 }
    );
  }

  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { credits: true },
    });

    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const previousCredits = user.credits;
    const newCredits = Math.max(0, previousCredits + delta);

    const updated = await prisma.user.update({
      where: { id: userId },
      data: { credits: newCredits },
      select: { credits: true },
    });

    return NextResponse.json({
      credits: updated.credits,
      delta,
      previous: previousCredits,
    });
  } catch (error) {
    console.error("Error updating credits:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
