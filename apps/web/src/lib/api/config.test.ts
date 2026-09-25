import { describe, expect, it } from "vitest";

import { safeNextPath } from "./config";

describe("safeNextPath", () => {
  it("keeps same-site relative paths", () => {
    expect(safeNextPath("/leads/abc?x=1")).toBe("/leads/abc?x=1");
  });

  it.each([null, "", "https://evil.example", "//evil.example", "/\\evil.example", "leads"])(
    "falls back for %s",
    (next) => {
      expect(safeNextPath(next)).toBe("/leads");
    },
  );
});
