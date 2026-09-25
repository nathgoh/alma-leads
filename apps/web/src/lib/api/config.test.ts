import { describe, expect, it } from "vitest";

import { safeNextPath } from "./config";

describe("safeNextPath", () => {
  it("keeps same-site relative paths", () => {
    expect(safeNextPath("/leads/abc?x=1")).toBe("/leads/abc?x=1");
  });

  it.each([
    null,
    "",
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "leads",
    // WHATWG strips leading control chars, so these used to resolve off-site.
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
  ])("falls back for %s", (next) => {
    expect(safeNextPath(next)).toBe("/leads");
  });

  it("resolves only to same-origin paths", () => {
    expect(new URL(safeNextPath("/\t/evil.example"), "https://app.example.com").origin).toBe(
      "https://app.example.com",
    );
  });
});
