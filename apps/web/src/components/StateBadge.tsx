import type { LeadState } from "@/lib/api/types";

import { cx } from "./ui";

const LABELS: Record<LeadState, string> = { PENDING: "Pending", REACHED_OUT: "Reached out" };

export function StateBadge({ state }: { state: LeadState }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        state === "PENDING"
          ? "bg-amber-50 text-amber-800 ring-amber-600/20"
          : "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
      )}
    >
      {LABELS[state]}
    </span>
  );
}
