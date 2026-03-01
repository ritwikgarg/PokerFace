"use client";

import type { RoomPlayer } from "@/types";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MAX_PLAYERS } from "@/lib/constants";
import { Check, Copy, Crown, Users } from "lucide-react";
import { toast } from "sonner";

interface LobbyProps {
  roomCode: string;
  players: RoomPlayer[];
  isHost: boolean;
  canStart: boolean;
  onStart: () => void;
  onReady: () => void;
  isReady: boolean;
}

export function Lobby({
  roomCode,
  players,
  isHost,
  canStart,
  onStart,
  onReady,
  isReady,
}: LobbyProps) {
  const copyCode = () => {
    navigator.clipboard.writeText(roomCode);
    toast.success("Room code copied!");
  };

  return (
    <div className="container max-w-2xl mx-auto py-8 px-4 space-y-6">
      {/* Room Code */}
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Game Lobby</CardTitle>
          <CardDescription>
            Share the room code with other players
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-3">
            <span className="text-4xl font-mono font-bold tracking-[0.3em] text-primary">
              {roomCode}
            </span>
            <Button variant="outline" size="icon" onClick={copyCode}>
              <Copy className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="h-4 w-4" />
            {players.length}/{MAX_PLAYERS} players
          </div>
        </CardContent>
      </Card>

      {/* Players list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Players</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {players.map((player) => (
            <div
              key={player.userId}
              className="flex items-center gap-3 p-3 rounded-lg bg-muted/30"
            >
              <Avatar className="h-10 w-10">
                <AvatarImage src={player.userImage} />
                <AvatarFallback>{player.userName.charAt(0)}</AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{player.userName}</span>
                  {player.isHost && (
                    <Crown className="h-3.5 w-3.5 text-yellow-500" />
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  {player.agentName}
                </span>
              </div>
              <Badge variant={player.isReady ? "default" : "secondary"}>
                {player.isReady ? (
                  <span className="flex items-center gap-1">
                    <Check className="h-3 w-3" /> Ready
                  </span>
                ) : (
                  "Not Ready"
                )}
              </Badge>
            </div>
          ))}
          {/* Empty slots */}
          {Array.from({ length: MAX_PLAYERS - players.length }).map((_, i) => (
            <div
              key={`empty-${i}`}
              className="flex items-center justify-center p-3 rounded-lg border-2 border-dashed border-muted text-muted-foreground text-sm"
            >
              Waiting for player...
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        {isHost ? (
          <Button
            className="flex-1"
            size="lg"
            onClick={onStart}
            disabled={!canStart}
          >
            {canStart ? "Start Game" : "Waiting for players to ready up..."}
          </Button>
        ) : (
          <Button
            className="flex-1"
            size="lg"
            variant={isReady ? "secondary" : "default"}
            onClick={onReady}
          >
            {isReady ? "Ready ✓" : "Ready Up"}
          </Button>
        )}
      </div>
    </div>
  );
}
