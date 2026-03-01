/*
  Warnings:

  - You are about to drop the column `opponentModelDepth` on the `Agent` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "Agent" DROP COLUMN "opponentModelDepth",
ADD COLUMN     "previousGamesHistory" INTEGER NOT NULL DEFAULT 0;
