/**
 * Cleanup script: removes rooms that have no players, are finished,
 * or have been idle (in "waiting" status) for over 1 hour.
 *
 * Usage:
 *   npx tsx scripts/cleanup-rooms.ts
 *
 * Can also be run as a cron job.
 */
import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import "dotenv/config";

const adapter = new PrismaPg({
  connectionString: process.env.DATABASE_URL!,
});
const prisma = new PrismaClient({ adapter });

const IDLE_THRESHOLD_MS = 15 * 60 * 1000; // 15 minutes

async function cleanupRooms() {
  const now = new Date();
  const idleCutoff = new Date(now.getTime() - IDLE_THRESHOLD_MS);

  // 1. Delete rooms with zero players
  const emptyRooms = await prisma.room.findMany({
    where: {
      players: { none: {} },
    },
    select: { id: true, code: true, status: true },
  });

  if (emptyRooms.length > 0) {
    await prisma.room.deleteMany({
      where: { id: { in: emptyRooms.map((r) => r.id) } },
    });
    console.log(
      `Deleted ${emptyRooms.length} empty room(s):`,
      emptyRooms.map((r) => r.code)
    );
  }

  // 2. Delete finished rooms
  const finishedRooms = await prisma.room.deleteMany({
    where: { status: "finished" },
  });
  if (finishedRooms.count > 0) {
    console.log(`Deleted ${finishedRooms.count} finished room(s).`);
  }

  // 3. Delete stale "waiting" rooms older than the idle threshold
  const staleRooms = await prisma.room.deleteMany({
    where: {
      status: "waiting",
      updatedAt: { lt: idleCutoff },
    },
  });
  if (staleRooms.count > 0) {
    console.log(`Deleted ${staleRooms.count} stale waiting room(s) (idle > 1h).`);
  }

  const total = emptyRooms.length + finishedRooms.count + staleRooms.count;
  if (total === 0) {
    console.log("No rooms to clean up.");
  } else {
    console.log(`Cleanup complete. ${total} room(s) removed.`);
  }
}

cleanupRooms()
  .catch((err) => {
    console.error("Cleanup failed:", err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
