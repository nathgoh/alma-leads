"use client";

import { useState } from "react";

import { browserApi } from "@/lib/api/browser";

import { Button } from "./ui";

/** Asks the API for a short-lived presigned URL at click time, then lets the browser download it. */
export function ResumeDownloadButton({ leadId, filename }: { leadId: string; filename: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const { data } = await browserApi.GET("/api/v1/leads/{lead_id}/resume", {
        params: { path: { lead_id: leadId } },
      });
      if (!data) {
        setError("Couldn't get the resume. Please try again.");
        return;
      }
      window.location.assign(data.url);
    } catch {
      setError("Couldn't get the resume. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-1">
      <Button type="button" variant="secondary" onClick={download} disabled={pending}>
        {pending ? "Preparing…" : `Download ${filename}`}
      </Button>
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
