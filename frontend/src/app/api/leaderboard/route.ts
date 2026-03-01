import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

// GET /api/leaderboard — top players
export async function GET() {
  const stats = await prisma.userStats.findMany({
    include: {
      user: {
        include: {
          agents: {
            orderBy: { updatedAt: "desc" },
            take: 1,
            select: { name: true },
          },
        },
      },
    },
    orderBy: [{ gamesWon: "desc" }, { totalProfit: "desc" }],
    take: 50,
  });

  const leaderboard = stats.map((s, i) => ({
    rank: i + 1,
    user: {
      id: s.user.id,
      name: s.user.name ?? "Anonymous",
      image: s.user.image ?? "",
      githubUsername: s.user.githubUsername || s.user.githubId,
    },
    agentName: s.user.agents[0]?.name ?? "No Agent",
    gamesPlayed: s.gamesPlayed,
    winRate: s.gamesPlayed > 0 ? Math.round((s.gamesWon / s.gamesPlayed) * 1000) / 10 : 0,
    totalEarnings: s.totalProfit,
    biggestPot: s.biggestPot,
  }));

  return NextResponse.json(leaderboard);
}
