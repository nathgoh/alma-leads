import type { Metadata } from "next";
import Link from "next/link";

import { LoginForm } from "@/components/LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4 py-12">
      <div className="mb-6 space-y-1">
        <p className="text-sm font-semibold tracking-wide text-zinc-500 uppercase">Alma</p>
        <h1 className="text-2xl font-semibold tracking-tight">Attorney sign in</h1>
      </div>
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <LoginForm next={next} />
      </div>
      <div className="mt-2 mb-8 space-y-2">
        <p className="text-sm font-light tracking-tight">
          Not an attorney?{" "}
          <Link href="/" className="font-medium text-zinc-900 underline underline-offset-4 hover:text-zinc-600">
            Submit your information for an assessment
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
