"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AgentForm } from "@/components/agent/agent-form";
import { useUserStore } from "@/stores/user-store";
import type { AgentConfigFormValues } from "@/lib/validators";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export default function EditAgentPage() {
  const router = useRouter();
  const params = useParams();
  const agentId = params.id as string;
  const agents = useUserStore((s) => s.agents);
  const fetchAgents = useUserStore((s) => s.fetchAgents);
  const updateAgentRemote = useUserStore((s) => s.updateAgentRemote);
  const credits = useUserStore((s) => s.credits);
  const fetchCredits = useUserStore((s) => s.fetchCredits);
  const [isLoading, setIsLoading] = useState(false);

  // Ensure agents and credits are loaded
  useEffect(() => {
    if (agents.length === 0) fetchAgents();
    fetchCredits();
  }, [agents.length, fetchAgents, fetchCredits]);

  const agent = agents.find((a) => a.id === agentId);

  if (!agent) {
    return (
      <AuthGuard>
        <div className="container max-w-3xl mx-auto py-8 px-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading agent...</p>
        </div>
      </AuthGuard>
    );
  }

  const handleSubmit = async (values: AgentConfigFormValues) => {
    setIsLoading(true);
    try {
      await updateAgentRemote(agentId, values);
      toast.success(`Agent "${values.name}" updated!`);
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update agent");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="container max-w-3xl mx-auto py-8 px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Edit Agent</h1>
          <p className="text-muted-foreground mt-2">
            Update your agent&apos;s configuration.
          </p>
        </div>
        <AgentForm
          defaultValues={agent}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          submitLabel="Save Changes"
          userCredits={credits}
        />
      </div>
    </AuthGuard>
  );
}
