"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserApi } from "@/lib/api/browser";
import type { LeadState } from "@/lib/api/types";

import { StateBadge } from "./StateBadge";
import { Button } from "./ui";

/** Optimistic PENDING → REACHED_OUT with rollback if the request fails. */
export function MarkReachedOutButton({
  leadId,
  initialState,
  compact = false,
}: {
  leadId: string;
  initialState: LeadState;
  compact?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<LeadState>(initialState);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function markReachedOut() {
    const previous = state;
    setState("REACHED_OUT");
    setPending(true);
    setError(null);
    try {
      const { response } = await browserApi.PATCH("/api/v1/leads/{lead_id}", {
        params: { path: { lead_id: leadId } },
        body: { state: "REACHED_OUT" },
      });
      if (response.status === 409) {
        // The only transition is PENDING → REACHED_OUT, so another attorney got here first.
        setError("This lead was already updated by someone else.");
      } else if (!response.ok) {
        setState(previous);
        setError("Couldn't update the lead. Please try again.");
      }
      router.refresh(); // pull the server's truth (timestamps, who, or the conflicting state)
    } catch {
      setState(previous);
      setError("Couldn't update the lead. Check your connection and try again.");
    } finally {
      setPending(false);
    }
  }

  if (state === "REACHED_OUT" && !pending) {
    return (
      <div>
        {!compact && <StateBadge state="REACHED_OUT" />}
        {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        type="button"
        variant={compact ? "secondary" : "primary"}
        className={compact ? "px-2.5 py-1 text-xs" : undefined}
        disabled={pending}
        onClick={markReachedOut}
      >
        {pending ? "Saving…" : "Mark as reached out"}
      </Button>
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
