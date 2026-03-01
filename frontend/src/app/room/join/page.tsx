"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { roomCodeSchema, type RoomCodeFormValues } from "@/lib/validators";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AgentPresetPicker } from "@/components/agent/agent-preset-picker";
import { useUserStore } from "@/stores/user-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { toast } from "sonner";
import { Users, ArrowRight } from "lucide-react";

export default function JoinRoomPage() {
  const router = useRouter();
  const agents = useUserStore((s) => s.agents);
  const fetchAgents = useUserStore((s) => s.fetchAgents);
  const selectedAgentId = useUserStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useUserStore((s) => s.setSelectedAgentId);
  const [isJoining, setIsJoining] = useState(false);

  useEffect(() => {
    if (agents.length === 0) fetchAgents();
  }, [agents.length, fetchAgents]);

  const form = useForm<RoomCodeFormValues>({
    resolver: zodResolver(roomCodeSchema),
    defaultValues: { code: "" },
  });

  const handleSubmit = async (values: RoomCodeFormValues) => {
    if (!selectedAgentId) {
      toast.error("Please select an agent first.");
      return;
    }
    setIsJoining(true);
    try {
      const res = await fetch(`/api/rooms/${values.code}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: selectedAgentId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error ?? "Failed to join room");
      }
      toast.success("Joining room...");
      router.push(`/room/${values.code}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to join room");
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <AuthGuard>
      <div className="container max-w-2xl mx-auto py-8 px-4 space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Join a Room</h1>
          <p className="text-muted-foreground mt-2">
            Enter a room code and select your agent to join an existing game.
          </p>
        </div>

        {/* Room Code */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Step 1: Enter Room Code</h2>
          <Form {...form}>
            <form className="flex gap-3">
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl>
                      <Input
                        placeholder="e.g. ABC123"
                        className="text-center text-2xl font-mono tracking-[0.2em] h-14 uppercase"
                        maxLength={6}
                        {...field}
                        onChange={(e) =>
                          field.onChange(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </form>
          </Form>
        </div>

        {/* Select Agent */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Step 2: Choose Your Agent</h2>
          <AgentPresetPicker
            agents={agents}
            selectedId={selectedAgentId}
            onSelect={(agent) => setSelectedAgentId(agent.id)}
            onCreateNew={() => router.push("/agent/new")}
          />
        </div>

        {/* Join Button */}
        <Button
          size="lg"
          className="w-full gap-2"
          onClick={() => form.handleSubmit(handleSubmit)()}
          disabled={isJoining || !selectedAgentId}
        >
          {isJoining ? (
            "Joining..."
          ) : (
            <>
              <Users className="h-5 w-5" />
              Join Room
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </AuthGuard>
  );
}
