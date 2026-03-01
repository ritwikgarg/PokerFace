"use client";

import type { LeaderboardEntry } from "@/types";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Trophy, Medal, Award } from "lucide-react";

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  currentUserId?: string;
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-yellow-500/20">
        <Trophy className="h-4 w-4 text-yellow-500" />
      </div>
    );
  if (rank === 2)
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-400/20">
        <Medal className="h-4 w-4 text-gray-400" />
      </div>
    );
  if (rank === 3)
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-600/20">
        <Award className="h-4 w-4 text-amber-600" />
      </div>
    );
  return (
    <div className="flex items-center justify-center w-8 h-8">
      <span className="text-sm font-mono text-muted-foreground">{rank}</span>
    </div>
  );
}

export function LeaderboardTable({ entries, currentUserId }: LeaderboardTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Rank</TableHead>
          <TableHead>Player</TableHead>
          <TableHead>Agent</TableHead>
          <TableHead className="text-right">Games</TableHead>
          <TableHead className="text-right">Win Rate</TableHead>
          <TableHead className="text-right">Earnings</TableHead>
          <TableHead className="text-right">Biggest Pot</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const isCurrentUser = entry.user.id === currentUserId;
          return (
            <TableRow
              key={entry.user.id}
              className={isCurrentUser ? "bg-primary/5 border-primary/20" : ""}
            >
              <TableCell>
                <RankBadge rank={entry.rank} />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={entry.user.image} />
                    <AvatarFallback>
                      {entry.user.name.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <span className="font-medium text-sm">{entry.user.name}</span>
                    <p className="text-xs text-muted-foreground">
                      @{entry.user.githubUsername}
                    </p>
                  </div>
                  {isCurrentUser && (
                    <Badge variant="outline" className="text-[10px] ml-1">
                      You
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <span className="text-sm">{entry.agentName}</span>
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {entry.gamesPlayed}
              </TableCell>
              <TableCell className="text-right">
                <span
                  className={`font-mono text-sm ${
                    entry.winRate >= 50
                      ? "text-green-400"
                      : entry.winRate >= 30
                      ? "text-yellow-400"
                      : "text-red-400"
                  }`}
                >
                  {entry.winRate.toFixed(1)}%
                </span>
              </TableCell>
              <TableCell className="text-right">
                <span
                  className={`font-mono text-sm font-medium ${
                    entry.totalEarnings >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {entry.totalEarnings >= 0 ? "+" : ""}$
                  {entry.totalEarnings.toLocaleString()}
                </span>
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                ${entry.biggestPot.toLocaleString()}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
