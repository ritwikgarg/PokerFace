import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import { prisma } from "@/lib/prisma";

if (!process.env.GITHUB_ID || !process.env.GITHUB_SECRET) {
  throw new Error(
    "Missing GitHub OAuth credentials. Please set GITHUB_ID and GITHUB_SECRET in .env.local"
  );
}

if (!process.env.NEXTAUTH_SECRET) {
  throw new Error("Missing NEXTAUTH_SECRET in .env.local");
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: process.env.NEXTAUTH_SECRET,
  providers: [
    GitHub({
      clientId: process.env.GITHUB_ID,
      clientSecret: process.env.GITHUB_SECRET,
      allowDangerousEmailAccountLinking: true,
    }),
  ],
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    async signIn({ user, profile }) {
      if (!profile) return true;

      const githubId = String(profile.id ?? profile.sub ?? "");
      const githubUsername = (profile as { login?: string }).login ?? "";
      if (!githubId) return false;

      // Upsert user into Supabase via Prisma
      await prisma.user.upsert({
        where: { githubId },
        update: {
          name: user.name ?? profile.name ?? undefined,
          email: user.email ?? (profile.email as string) ?? undefined,
          image: user.image ?? (profile.avatar_url as string) ?? undefined,
          githubUsername: githubUsername || undefined,
        },
        create: {
          githubId,
          githubUsername,
          name: user.name ?? profile.name ?? "",
          email: user.email ?? (profile.email as string) ?? null,
          image: user.image ?? (profile.avatar_url as string) ?? null,
        },
      });

      // Also create a UserStats row if it doesn't exist
      const dbUser = await prisma.user.findUnique({ where: { githubId } });
      if (dbUser) {
        await prisma.userStats.upsert({
          where: { userId: dbUser.id },
          update: {},
          create: { userId: dbUser.id },
        });
      }

      return true;
    },
    async jwt({ token, profile }) {
      if (profile) {
        const githubId = String(profile.id ?? profile.sub ?? "");
        // Look up the Prisma user to store the DB id in the token
        const dbUser = await prisma.user.findUnique({ where: { githubId } });
        if (dbUser) {
          token.dbUserId = dbUser.id;
        }
        token.githubId = githubId;
        token.githubUsername = (profile as { login?: string }).login || "";
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = (token.dbUserId as string) ?? "";
        session.user.name = token.name;
        (session.user as { githubUsername?: string }).githubUsername =
          token.githubUsername as string;
      }
      return session;
    },
  },
  trustHost: true,
});
