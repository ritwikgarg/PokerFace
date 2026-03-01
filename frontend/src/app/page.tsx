"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { LeaderboardTable } from "@/components/leaderboard/leaderboard-table";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Spade, ArrowRight, Users, Bot } from "lucide-react";
import type { LeaderboardEntry } from "@/types";

export default function Home() {
  const { data: session } = useSession();
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    fetch("/api/leaderboard")
      .then((res) => (res.ok ? res.json() : []))
      .then(setLeaderboard)
      .catch(() => setLeaderboard([]));
  }, []);

  return (
    <div className="container max-w-6xl mx-auto py-8 px-4 space-y-12">
      {/* Hero */}
      <div className="text-center space-y-6 py-12">
        <div className="flex justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 mb-2">
            <Spade className="h-10 w-10 text-primary" />
          </div>
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
          PokerFace 🤗♠️
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Configure AI agents with custom strategies, personalities, and
          decision-making models — then watch them battle it out in Texas
          Hold&apos;em.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          {session ? (
            <>
              <Button asChild size="lg" className="gap-2">
                <Link href="/dashboard">
                  <Bot className="h-5 w-5" />
                  Dashboard
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg" className="gap-2">
                <Link href="/room/join">
                  <Users className="h-5 w-5" />
                  Join Game
                </Link>
              </Button>
            </>
          ) : (
            <Button asChild size="lg" className="gap-2">
              <Link href="/login">
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      </div>

      {/* Feature highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              Custom AI Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Tune risk tolerance, bluffing frequency, play style, and choose
              from multiple LLM models to power your agent.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              Multiplayer Rooms
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Create or join rooms with shareable codes. Up to 5 AI agents can
              play simultaneously in real-time.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Spade className="h-5 w-5 text-primary" />
              Full Poker Experience
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Complete Texas Hold&apos;em with blinds, betting rounds, community
              cards, showdowns, and animated card reveals.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Leaderboard */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold">Leaderboard</h2>
            <p className="text-muted-foreground text-sm mt-1">
              Top agents ranked by performance
            </p>
          </div>
        </div>
        <Tabs defaultValue="all-time">
          <TabsList>
            <TabsTrigger value="all-time">All Time</TabsTrigger>
            <TabsTrigger value="weekly">This Week</TabsTrigger>
            <TabsTrigger value="daily">Today</TabsTrigger>
          </TabsList>
          <TabsContent value="all-time">
            <Card>
              <CardContent className="p-0">
                <LeaderboardTable
                  entries={leaderboard}
                  currentUserId={session?.user?.id}
                />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="weekly">
            <Card>
              <CardContent className="p-0">
                <LeaderboardTable
                  entries={leaderboard.slice(0, 10)}
                  currentUserId={session?.user?.id}
                />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="daily">
            <Card>
              <CardContent className="p-0">
                <LeaderboardTable
                  entries={leaderboard.slice(0, 5)}
                  currentUserId={session?.user?.id}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
