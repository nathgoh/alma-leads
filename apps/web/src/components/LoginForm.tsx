"use client";

import { useState } from "react";

import { browserApi } from "@/lib/api/browser";
import { safeNextPath } from "@/lib/api/config";
import { parseApiError } from "@/lib/api/errors";

import { Alert, Button, Field, inputClass } from "./ui";

export function LoginForm({ next }: { next?: string }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setPending(true);
    setError(null);
    try {
      const { error: body, response } = await browserApi.POST("/api/v1/auth/login", {
        body: { email: String(form.get("email") ?? ""), password: String(form.get("password") ?? "") },
      });
      if (response.ok) {
        // Full navigation so server components re-render with the new cookie.
        window.location.assign(safeNextPath(next));
        return;
      }
      setError(
        response.status === 401 || response.status === 422
          ? "Invalid email or password"
          : parseApiError(response.status, body).general,
      );
    } catch {
      setError("Couldn't sign in. Check your connection and try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" aria-label="Sign in">
      {error && <Alert>{error}</Alert>}
      <Field id="email" label="Email">
        <input id="email" name="email" type="email" autoComplete="username" required className={inputClass(false)} />
      </Field>
      <Field id="password" label="Password">
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className={inputClass(false)}
        />
      </Field>
      <Button type="submit" disabled={pending} className="w-full">
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
