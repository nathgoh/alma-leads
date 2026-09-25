"use client";

// Rendered in the viewer's time zone. The server pass renders UTC; the client re-renders local.
export function LocalTime({ iso }: { iso: string }) {
  const date = new Date(iso);
  const text = date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  return (
    <time dateTime={iso} title={date.toISOString()} suppressHydrationWarning>
      {text}
    </time>
  );
}
