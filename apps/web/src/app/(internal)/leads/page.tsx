import type { Metadata } from "next";
import Link from "next/link";

import { LocalTime } from "@/components/LocalTime";
import { MarkReachedOutButton } from "@/components/MarkReachedOutButton";
import { StateBadge } from "@/components/StateBadge";
import { cx } from "@/components/ui";
import { serverApi, unwrap } from "@/lib/api/server";
import type { LeadState } from "@/lib/api/types";

export const metadata: Metadata = { title: "Leads" };

const PAGE_SIZE = 20;
const TABS = [
  { key: "PENDING", label: "Pending" },
  { key: "REACHED_OUT", label: "Reached out" },
  { key: "all", label: "All" },
] as const;
type Tab = (typeof TABS)[number]["key"];

function parseTab(v: string | undefined): Tab {
  return TABS.some((t) => t.key === v) ? (v as Tab) : "PENDING";
}

function href(tab: Tab, page = 1): string {
  const params = new URLSearchParams({ state: tab });
  if (page > 1) params.set("page", String(page));
  return `/leads?${params}`;
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string; page?: string }>;
}) {
  const sp = await searchParams;
  const tab = parseTab(sp.state);
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);

  const api = await serverApi();
  const data = unwrap(
    await api.GET("/api/v1/leads", {
      params: {
        query: {
          page,
          pageSize: PAGE_SIZE,
          state: tab === "all" ? undefined : (tab as LeadState),
          sort: "newest",
        },
      },
    }),
    href(tab, page),
  );
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
        <nav aria-label="Filter by state" className="flex gap-1 rounded-lg bg-zinc-100 p-1">
          {TABS.map((t) => (
            <Link
              key={t.key}
              href={href(t.key)}
              aria-current={t.key === tab ? "page" : undefined}
              className={cx(
                "rounded-md px-3 py-1.5 text-sm font-medium",
                t.key === tab ? "bg-white shadow-sm" : "text-zinc-600 hover:text-zinc-900",
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
      </div>

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table className="min-w-full divide-y divide-zinc-200 text-sm">
          <thead className="bg-zinc-50 text-left text-xs font-medium tracking-wide text-zinc-500 uppercase">
            <tr>
              <th scope="col" className="px-4 py-3">Name</th>
              <th scope="col" className="px-4 py-3">Email</th>
              <th scope="col" className="px-4 py-3">Submitted</th>
              <th scope="col" className="px-4 py-3">State</th>
              <th scope="col" className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-zinc-500">
                  No leads here yet.
                </td>
              </tr>
            )}
            {data.items.map((lead) => (
              <tr key={lead.id} className="hover:bg-zinc-50">
                <td className="px-4 py-3 font-medium">
                  <Link href={`/leads/${lead.id}`} className="hover:underline">
                    {lead.firstName} {lead.lastName}
                  </Link>
                </td>
                <td className="px-4 py-3 text-zinc-600">{lead.email}</td>
                <td className="px-4 py-3 whitespace-nowrap text-zinc-600">
                  <LocalTime iso={lead.createdAt} />
                </td>
                <td className="px-4 py-3">
                  <StateBadge state={lead.state} />
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-3">
                    {lead.state === "PENDING" && (
                      <MarkReachedOutButton key={lead.state} leadId={lead.id} initialState={lead.state} compact />
                    )}
                    <Link href={`/leads/${lead.id}`} className="text-sm text-zinc-600 hover:text-zinc-900">
                      View →
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <span className="text-zinc-600">
            Page {page} of {pages} · {data.total} leads
          </span>
          <div className="flex gap-2">
            {page > 1 && (
              <Link className="rounded-md border border-zinc-300 bg-white px-3 py-1.5" href={href(tab, page - 1)}>
                Previous
              </Link>
            )}
            {page < pages && (
              <Link className="rounded-md border border-zinc-300 bg-white px-3 py-1.5" href={href(tab, page + 1)}>
                Next
              </Link>
            )}
          </div>
        </nav>
      )}
    </div>
  );
}
