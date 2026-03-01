"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { agentConfigSchema, type AgentConfigFormValues } from "@/lib/validators";
import { DEFAULT_AGENT_VALUES, LLM_MODELS, PLAY_STYLES, HISTORY_COSTS } from "@/lib/constants";
import { API_URL } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Bot, Brain, Flame, Sparkles, Coins } from "lucide-react";

interface AgentFormProps {
  defaultValues?: Partial<AgentConfigFormValues>;
  onSubmit: (values: AgentConfigFormValues) => void;
  isLoading?: boolean;
  submitLabel?: string;
  userCredits?: number | null;
}

export function AgentForm({
  defaultValues,
  onSubmit,
  isLoading = false,
  submitLabel = "Save Agent",
  userCredits,
}: AgentFormProps) {
  // Fetch selectable models from backend (falls back to hardcoded constants)
  const [models, setModels] = useState(LLM_MODELS);
  const [historyCosts, setHistoryCosts] = useState<Record<number, number>>(HISTORY_COSTS);

  useEffect(() => {
    fetch(`${API_URL}/api/models/selectable`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.models?.length) {
          setModels(data.models);
        }
        if (data?.historyCosts) {
          const parsed: Record<number, number> = {};
          for (const [k, v] of Object.entries(data.historyCosts)) {
            parsed[Number(k)] = v as number;
          }
          setHistoryCosts(parsed);
        }
      })
      .catch(() => {
        // Use fallback constants on error
      });
  }, []);

  // Build model cost lookup from the fetched models list
  const modelCosts: Record<string, number> = {};
  for (const m of models) {
    modelCosts[m.value] = m.cost;
  }

  const form = useForm<AgentConfigFormValues>({
    resolver: zodResolver(agentConfigSchema),
    defaultValues: { ...DEFAULT_AGENT_VALUES, ...defaultValues },
  });

  const watchedModel = form.watch("baseLLM");
  const watchedHistory = form.watch("previousGamesHistory");
  const calcCost = (model: string, history: number) =>
    (modelCosts[model] ?? 0) + (historyCosts[history] ?? 0);
  const totalCost = calcCost(watchedModel, watchedHistory);

  // For edits: cost difference from original config
  const originalCost = defaultValues
    ? calcCost(defaultValues.baseLLM ?? DEFAULT_AGENT_VALUES.baseLLM, defaultValues.previousGamesHistory ?? DEFAULT_AGENT_VALUES.previousGamesHistory)
    : 0;
  const costDiff = defaultValues ? totalCost - originalCost : totalCost;
  const canAfford = userCredits == null || userCredits >= costDiff;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        {/* ---- Identity ---- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              Identity
            </CardTitle>
            <CardDescription>
              Name your agent and give it a personality.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Agent Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. The Shark" {...field} />
                  </FormControl>
                  <FormDescription>
                    A memorable name for your AI poker agent.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="personalityPrompt"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Personality Prompt</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="e.g. You are a seasoned Vegas card shark who speaks in short, confident phrases and never shows weakness..."
                      className="min-h-[100px] resize-y"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Optional prompt to shape the agent&apos;s personality and communication style.
                    ({field.value?.length ?? 0}/500)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* ---- Strategy ---- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Strategy
            </CardTitle>
            <CardDescription>
              Configure how your agent approaches the game.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-8">
            {/* Play Style */}
            <FormField
              control={form.control}
              name="playStyle"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Play Style</FormLabel>
                  <FormControl>
                    <RadioGroup
                      value={field.value}
                      onValueChange={field.onChange}
                      className="grid grid-cols-1 sm:grid-cols-2 gap-3"
                    >
                      {PLAY_STYLES.map((style) => (
                        <Label
                          key={style.value}
                          htmlFor={style.value}
                          className={`flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors hover:bg-accent ${
                            field.value === style.value
                              ? "border-primary bg-primary/5"
                              : "border-border"
                          }`}
                        >
                          <RadioGroupItem
                            value={style.value}
                            id={style.value}
                            className="mt-0.5"
                          />
                          <div>
                            <div className="font-medium text-sm">{style.label}</div>
                            <div className="text-xs text-muted-foreground mt-1">
                              {style.description}
                            </div>
                          </div>
                        </Label>
                      ))}
                    </RadioGroup>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Risk Tolerance */}
            <FormField
              control={form.control}
              name="riskTolerance"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center justify-between">
                    <FormLabel className="flex items-center gap-2">
                      <Flame className="h-4 w-4 text-orange-500" />
                      Risk Tolerance
                    </FormLabel>
                    <span className="text-sm font-mono text-muted-foreground">
                      {field.value}%
                    </span>
                  </div>
                  <FormControl>
                    <Slider
                      value={[field.value]}
                      onValueChange={(v) => field.onChange(v[0])}
                      min={0}
                      max={100}
                      step={1}
                      className="py-2"
                    />
                  </FormControl>
                  <FormDescription>
                    How willing the agent is to take risks. Low = conservative, High = aggressive.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Deception / Bluff Frequency */}
            <FormField
              control={form.control}
              name="deception"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center justify-between">
                    <FormLabel className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-purple-500" />
                      Deception (Bluff Frequency)
                    </FormLabel>
                    <span className="text-sm font-mono text-muted-foreground">
                      {field.value}%
                    </span>
                  </div>
                  <FormControl>
                    <Slider
                      value={[field.value]}
                      onValueChange={(v) => field.onChange(v[0])}
                      min={0}
                      max={100}
                      step={1}
                      className="py-2"
                    />
                  </FormControl>
                  <FormDescription>
                    How often the agent will attempt to bluff. Low = honest, High = deceptive.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Previous Games History — toggle + slider */}
            <FormField
              control={form.control}
              name="previousGamesHistory"
              render={({ field }) => {
                const isEnabled = field.value > 0;
                const LEVEL_DESCRIPTIONS: Record<number, string> = {
                  0: "Disabled — no game history retrieval",
                  1: "Minimal — 1 query, 2 results, brief context",
                  2: "Moderate — 2 queries, 4 results",
                  3: "Full — all queries (opponents, self-learnings, board), 10+ results",
                };
                return (
                  <FormItem>
                    <div className="flex items-center justify-between">
                      <FormLabel className="flex items-center gap-2">
                        <img
                          src="/image.png"
                          alt="Supermemory"
                          className="h-4 w-4 rounded-sm object-contain"
                        />
                        Previous Games History
                      </FormLabel>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={isEnabled}
                        onClick={() => field.onChange(isEnabled ? 0 : 1)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                          isEnabled ? "bg-primary" : "bg-muted"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            isEnabled ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                    {isEnabled && (
                      <div className="space-y-2 pt-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">
                            Level {field.value}
                          </span>
                          <span className="text-sm font-mono text-muted-foreground">
                            <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                              {historyCosts[field.value] === 0 ? "Free" : `${historyCosts[field.value]} credits`}
                            </span>
                          </span>
                        </div>
                        <FormControl>
                          <Slider
                            value={[field.value]}
                            onValueChange={(v) => field.onChange(v[0])}
                            min={1}
                            max={3}
                            step={1}
                            className="py-2"
                          />
                        </FormControl>
                      </div>
                    )}
                    <FormDescription>
                      {LEVEL_DESCRIPTIONS[field.value]}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />
          </CardContent>
        </Card>

        {/* ---- Model ---- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Base Model
            </CardTitle>
            <CardDescription>
              Choose the LLM that powers your agent&apos;s decision-making.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FormField
              control={form.control}
              name="baseLLM"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>LLM Model</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {models.map((model) => {
                        const cost = modelCosts[model.value] ?? 0;
                        return (
                          <SelectItem key={model.value} value={model.value}>
                            <div className="flex items-center justify-between gap-3 w-full">
                              <div className="flex flex-col">
                                <span>{model.label}</span>
                                <span className="text-xs text-muted-foreground">
                                  {model.description}
                                </span>
                              </div>
                              <Badge variant={cost === 0 ? "secondary" : "outline"} className="ml-auto shrink-0 text-xs">
                                {cost === 0 ? "Free" : `${cost} cr`}
                              </Badge>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* Cost Summary */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Coins className="h-5 w-5 text-yellow-500" />
                <span className="font-semibold">
                  {defaultValues ? "Config Change Cost" : "Agent Cost"}
                </span>
              </div>
              <div className="text-right">
                {defaultValues ? (
                  <span className={`text-lg font-bold ${costDiff > 0 ? "text-red-500" : costDiff < 0 ? "text-green-500" : "text-muted-foreground"}`}>
                    {costDiff > 0 ? `+${costDiff}` : costDiff < 0 ? `${costDiff} (refund)` : "No change"}
                    {costDiff !== 0 && " credits"}
                  </span>
                ) : (
                  <span className={`text-lg font-bold ${totalCost === 0 ? "text-green-500" : "text-yellow-600 dark:text-yellow-400"}`}>
                    {totalCost === 0 ? "Free" : `${totalCost} credits`}
                  </span>
                )}
                {userCredits != null && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Balance: {userCredits.toLocaleString()} credits
                  </p>
                )}
              </div>
            </div>
            {!canAfford && (
              <p className="text-sm text-destructive mt-2">
                Insufficient credits. You need {costDiff} credits but only have {userCredits?.toLocaleString()}.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Button type="submit" size="lg" disabled={isLoading || !canAfford}>
            {isLoading ? "Saving..." : submitLabel}
          </Button>
        </div>
      </form>
    </Form>
  );
}
