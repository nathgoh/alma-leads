import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { LocalTime } from "@/components/LocalTime";
import { MarkReachedOutButton } from "@/components/MarkReachedOutButton";
import { ResumeDownloadButton } from "@/components/ResumeDownloadButton";
import { StateBadge } from "@/components/StateBadge";
import { serverApi, unwrap } from "@/lib/api/server";
import type { EmailLog } from "@/lib/api/types";

export const metadata: Metadata = { title: "Lead" };

const KIND_LABELS: Record<EmailLog["kind"], string> = {
  PROSPECT_CONFIRMATION: "Prospect confirmation",
  ATTORNEY_NOTIFICATION: "Attorney notification",
};

function formatBytes(n: number): string {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-zinc-500">{label}</dt>
      <dd className="text-sm sm:col-span-2">{children}</dd>
    </div>
  );
}

export default async function LeadDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const api = await serverApi();
  const result = await api.GET("/api/v1/leads/{lead_id}", { params: { path: { lead_id: id } } });
  if (result.response.status === 404) notFound();
  const lead = unwrap(result, `/leads/${id}`);

  return (
    <div className="space-y-6">
      <Link href="/leads" className="text-sm text-zinc-600 hover:text-zinc-900">
        ← All leads
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {lead.firstName} {lead.lastName}
          </h1>
          <StateBadge state={lead.state} />
        </div>
        {lead.state === "PENDING" && (
          <MarkReachedOutButton key={lead.state} leadId={lead.id} initialState={lead.state} />
        )}
      </div>

      <section className="rounded-xl border border-zinc-200 bg-white px-6 py-2">
        <dl className="divide-y divide-zinc-100">
          <Row label="First name">{lead.firstName}</Row>
          <Row label="Last name">{lead.lastName}</Row>
          <Row label="Email">
            <a href={`mailto:${lead.email}`} className="underline-offset-4 hover:underline">
              {lead.email}
            </a>
          </Row>
          <Row label="Submitted">
            <LocalTime iso={lead.createdAt} />
          </Row>
          <Row label="Resume">
            <div className="space-y-2">
              <p className="text-zinc-600">
                {lead.resumeName} · {formatBytes(lead.resumeSize)}
              </p>
              <ResumeDownloadButton leadId={lead.id} filename={lead.resumeName} />
            </div>
          </Row>
          {lead.state === "REACHED_OUT" && (
            <Row label="Reached out">
              {lead.reachedOutAt && <LocalTime iso={lead.reachedOutAt} />}
              {lead.reachedOutBy && <span className="text-zinc-600"> by {lead.reachedOutBy.name}</span>}
            </Row>
          )}
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-zinc-700">Email delivery</h2>
        <ul className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white text-sm">
          {lead.emails.length === 0 && <li className="px-4 py-3 text-zinc-500">No emails recorded yet.</li>}
          {lead.emails.map((e) => (
            <li key={`${e.kind}-${e.recipient}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <span>
                {KIND_LABELS[e.kind]} <span className="text-zinc-500">→ {e.recipient}</span>
              </span>
              <span className="text-zinc-600">
                {e.status === "SENT" && e.sentAt ? (
                  <>
                    Sent <LocalTime iso={e.sentAt} />
                  </>
                ) : (
                  <>
                    {e.status === "FAILED" ? "Failed" : "Pending"} · {e.attempts} attempt{e.attempts === 1 ? "" : "s"}
                    {e.error && <span className="block text-xs text-red-700">{e.error}</span>}
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
