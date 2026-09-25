import { headers } from "next/headers";
import Link from "next/link";
import type { ReactNode } from "react";

import { LogoutButton } from "@/components/LogoutButton";
import { serverApi, unwrap } from "@/lib/api/server";

export default async function InternalLayout({ children }: { children: ReactNode }) {
  const api = await serverApi();
  const currentPath = (await headers()).get("x-pathname") ?? "/leads";
  const me = unwrap(await api.GET("/api/v1/auth/me"), currentPath);

  return (
    <div className="min-h-screen">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link href="/leads" className="font-semibold tracking-tight">
            Alma <span className="font-normal text-zinc-500">Leads</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-600">{me.name}</span>
            <LogoutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
