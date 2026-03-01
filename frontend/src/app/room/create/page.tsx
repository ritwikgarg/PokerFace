"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AgentPresetPicker } from "@/components/agent/agent-preset-picker";
import { useUserStore } from "@/stores/user-store";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "sonner";
import { Copy, ArrowRight, Plus } from "lucide-react";

export default function CreateRoomPage() {
  const router = useRouter();
  const agents = useUserStore((s) => s.agents);
  const fetchAgents = useUserStore((s) => s.fetchAgents);
  const selectedAgentId = useUserStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useUserStore((s) => s.setSelectedAgentId);
  const [roomCode, setRoomCode] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (agents.length === 0) fetchAgents();
  }, [agents.length, fetchAgents]);

  const handleCreate = async () => {
    if (!selectedAgentId) {
      toast.error("Please select an agent first.");
      return;
    }
    setIsCreating(true);
    try {
      const res = await fetch("/api/rooms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: selectedAgentId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error ?? "Failed to create room");
      }
      const room = await res.json();
      setRoomCode(room.code);
      toast.success("Room created!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create room");
    } finally {
      setIsCreating(false);
    }
  };

  const copyCode = () => {
    if (roomCode) {
      navigator.clipboard.writeText(roomCode);
      toast.success("Room code copied!");
    }
  };

  return (
    <AuthGuard>
      <div className="container max-w-2xl mx-auto py-8 px-4 space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Create a Room</h1>
          <p className="text-muted-foreground mt-2">
            Select your agent and create a new poker game. Share the code with
            others so they can join.
          </p>
        </div>

        {!roomCode ? (
          <>
            {/* Step 1: Select Agent */}
            <div>
              <h2 className="text-lg font-semibold mb-4">
                Step 1: Choose Your Agent
              </h2>
              <AgentPresetPicker
                agents={agents}
                selectedId={selectedAgentId}
                onSelect={(agent) => setSelectedAgentId(agent.id)}
                onCreateNew={() => router.push("/agent/new")}
              />
            </div>

            {/* Step 2: Create */}
            <Button
              size="lg"
              className="w-full gap-2"
              onClick={handleCreate}
              disabled={!selectedAgentId || isCreating}
            >
              {isCreating ? (
                "Creating..."
              ) : (
                <>
                  <Plus className="h-5 w-5" />
                  Create Room
                </>
              )}
            </Button>
          </>
        ) : (
          <Card>
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Room Created!</CardTitle>
              <CardDescription>
                Share this code with other players so they can join.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-center gap-4">
                <div className="text-5xl font-mono font-bold tracking-[0.3em] text-primary">
                  {roomCode}
                </div>
                <Button variant="outline" size="icon" onClick={copyCode}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  className="flex-1 gap-2"
                  onClick={() => router.push(`/room/${roomCode}`)}
                >
                  Enter Lobby
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={copyCode}
                >
                  <Copy className="h-4 w-4 mr-2" />
                  Copy Invite Link
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AuthGuard>
  );
}
