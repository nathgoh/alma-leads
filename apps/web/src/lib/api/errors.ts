import type { ApiErrorBody } from "./types";

export type FieldErrors = Record<string, string>;

/** Split a FastAPI error body into per-field messages (by the last `loc` segment) + a general one. */
export function parseApiError(
  status: number,
  body: unknown,
): { fields: FieldErrors; general: string | null } {
  const detail = (body as ApiErrorBody | undefined)?.detail;
  const fields: FieldErrors = {};
  if (Array.isArray(detail)) {
    for (const err of detail) {
      const key = err.loc[err.loc.length - 1];
      if (typeof key === "string" && !(key in fields)) fields[key] = err.msg.replace(/^Value error, /, "");
    }
  }
  if (Object.keys(fields).length > 0) return { fields, general: null };
  if (status === 429) return { fields, general: "Too many attempts. Please wait a few minutes and try again." };
  if (typeof detail === "string") return { fields, general: detail };
  return { fields, general: "Something went wrong. Please try again." };
}
