"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
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
import { Separator } from "@/components/ui/separator";
import { Plus, Users, ArrowRight, Trophy, Gamepad2, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { toast } from "sonner";

export default function DashboardPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const agents = useUserStore((s) => s.agents);
  const isLoading = useUserStore((s) => s.isLoading);
  const selectedAgentId = useUserStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useUserStore((s) => s.setSelectedAgentId);
  const fetchAgents = useUserStore((s) => s.fetchAgents);
  const deleteAgent = useUserStore((s) => s.deleteAgent);

  // Fetch agents from DB on mount
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Force first-time users to create an agent (only after loading)
  useEffect(() => {
    if (!isLoading && agents.length === 0) {
      const timer = setTimeout(() => {
        router.push("/agent/new");
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [agents.length, isLoading, router]);

  return (
    <AuthGuard>
      <div className="container max-w-6xl mx-auto py-8 px-4 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">
            Welcome back, {session?.user?.name?.split(" ")[0] ?? "Player"}
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage your agents and jump into a game.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card
            className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50"
            onClick={() => router.push("/room/create")}
          >
            <CardHeader className="pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10 mb-2">
                <Plus className="h-5 w-5 text-green-500" />
              </div>
              <CardTitle className="text-lg">Create Room</CardTitle>
              <CardDescription>
                Start a new poker game and invite others.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="ghost" className="gap-2 p-0 h-auto text-primary">
                Create <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50"
            onClick={() => router.push("/room/join")}
          >
            <CardHeader className="pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 mb-2">
                <Users className="h-5 w-5 text-blue-500" />
              </div>
              <CardTitle className="text-lg">Join Room</CardTitle>
              <CardDescription>
                Enter a room code to join an existing game.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="ghost" className="gap-2 p-0 h-auto text-primary">
                Join <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer transition-all hover:shadow-md hover:border-primary/50"
            onClick={() => router.push("/")}
          >
            <CardHeader className="pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-500/10 mb-2">
                <Trophy className="h-5 w-5 text-yellow-500" />
              </div>
              <CardTitle className="text-lg">Leaderboard</CardTitle>
              <CardDescription>
                See top agents and player rankings.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="ghost" className="gap-2 p-0 h-auto text-primary">
                View <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>

        <Separator />

        {/* My Agents */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Gamepad2 className="h-5 w-5" />
                My Agents
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Select an agent to use in your next game, or create a new one.
              </p>
            </div>
          </div>
          <AgentPresetPicker
            agents={agents}
            selectedId={selectedAgentId}
            onSelect={(agent) => setSelectedAgentId(agent.id)}
            onCreateNew={() => router.push("/agent/new")}
            onEdit={(agent) => router.push(`/agent/${agent.id}`)}
            onDelete={async (agent) => {
              try {
                await deleteAgent(agent.id);
                toast.success(`Agent "${agent.name}" deleted`);
              } catch {
                toast.error("Failed to delete agent");
              }
            }}
          />
        </div>

        <Separator />

        {/* Recent Games (placeholder) */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Recent Games</h2>
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <Gamepad2 className="h-12 w-12 text-muted-foreground/30 mb-4" />
              <p className="text-muted-foreground">No games played yet.</p>
              <p className="text-sm text-muted-foreground">
                Create or join a room to start playing!
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </AuthGuard>
  );
}
