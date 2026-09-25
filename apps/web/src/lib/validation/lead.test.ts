// Same edge cases as the API tests (apps/api/tests/test_leads_public.py, test_files.py).
import { describe, expect, it } from "vitest";

import { MAX_RESUME_BYTES, leadSchema } from "./lead";

const pdf = (size = 100, name = "cv.pdf") => new File([new Uint8Array(size)], name, { type: "application/pdf" });
const valid = { firstName: "Ada", lastName: "Lovelace", email: "ada@example.com", resume: pdf() };

function issues(input: Record<string, unknown>) {
  const result = leadSchema.safeParse(input);
  return result.success ? {} : Object.fromEntries(result.error.issues.map((i) => [i.path[0], i.message]));
}

describe("leadSchema", () => {
  it("accepts a valid lead and trims names", () => {
    const parsed = leadSchema.parse({ ...valid, firstName: "  Ada " });
    expect(parsed.firstName).toBe("Ada");
  });

  it.each(["cv.pdf", "cv.DOC", "resume.docx"])("accepts %s", (name) => {
    expect(issues({ ...valid, resume: pdf(100, name) })).toEqual({});
  });

  it("rejects blank names (whitespace only)", () => {
    expect(issues({ ...valid, firstName: "   " })).toHaveProperty("firstName", "First name is required");
  });

  it("rejects names over 100 characters", () => {
    expect(issues({ ...valid, lastName: "x".repeat(101) })).toHaveProperty("lastName");
    expect(issues({ ...valid, lastName: "x".repeat(100) })).toEqual({});
  });

  it("rejects bad email", () => {
    expect(issues({ ...valid, email: "not-an-email" })).toHaveProperty("email", "Enter a valid email address");
  });

  it("requires a file", () => {
    expect(issues({ ...valid, resume: undefined })).toHaveProperty("resume", "Please attach your resume");
  });

  it("rejects other file types", () => {
    expect(issues({ ...valid, resume: pdf(100, "setup.exe") })).toHaveProperty(
      "resume",
      "Resume must be a PDF, DOC, or DOCX file",
    );
  });

  it("rejects files over the size limit", () => {
    expect(issues({ ...valid, resume: pdf(MAX_RESUME_BYTES + 1) })).toHaveProperty("resume");
    expect(issues({ ...valid, resume: pdf(MAX_RESUME_BYTES) })).toEqual({});
  });

  it("rejects empty files", () => {
    expect(issues({ ...valid, resume: pdf(0) })).toHaveProperty("resume", "File is empty");
  });
});
