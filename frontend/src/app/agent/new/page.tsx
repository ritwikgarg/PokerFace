"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/auth/auth-guard";
import { AgentForm } from "@/components/agent/agent-form";
import { useUserStore } from "@/stores/user-store";
import type { AgentConfigFormValues } from "@/lib/validators";
import { toast } from "sonner";

export default function NewAgentPage() {
  const router = useRouter();
  const createAgent = useUserStore((s) => s.createAgent);
  const credits = useUserStore((s) => s.credits);
  const fetchCredits = useUserStore((s) => s.fetchCredits);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchCredits();
  }, [fetchCredits]);

  const handleSubmit = async (values: AgentConfigFormValues) => {
    setIsLoading(true);
    try {
      await createAgent(values);
      toast.success(`Agent "${values.name}" created!`);
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthGuard>
      <div className="container max-w-3xl mx-auto py-8 px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Create New Agent</h1>
          <p className="text-muted-foreground mt-2">
            Configure your AI poker agent&apos;s strategy, personality, and
            decision-making model.
          </p>
        </div>
        <AgentForm onSubmit={handleSubmit} isLoading={isLoading} submitLabel="Create Agent" userCredits={credits} />
      </div>
    </AuthGuard>
  );
}
