"use client";

import { browserApi } from "@/lib/api/browser";

export function LogoutButton() {
  return (
    <button
      type="button"
      className="text-sm text-zinc-600 underline-offset-4 hover:text-zinc-900 hover:underline"
      onClick={async () => {
        await browserApi.POST("/api/v1/auth/logout");
        window.location.assign("/login");
      }}
    >
      Sign out
    </button>
  );
}
