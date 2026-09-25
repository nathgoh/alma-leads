import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeadForm } from "./LeadForm";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function fill(user: ReturnType<typeof userEvent.setup>, file?: File) {
  await user.type(screen.getByLabelText("First name"), "Ada");
  await user.type(screen.getByLabelText("Last name"), "Lovelace");
  await user.type(screen.getByLabelText("Email"), "ada@example.com");
  if (file) await user.upload(screen.getByLabelText("Resume / CV"), file);
}

const pdf = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });

describe("LeadForm", () => {
  it("shows field-level errors and doesn't submit when invalid", async () => {
    const user = userEvent.setup();
    render(<LeadForm />);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByText("First name is required")).toBeInTheDocument();
    expect(screen.getByText("Last name is required")).toBeInTheDocument();
    expect(screen.getByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Please attach your resume")).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an oversized file in the browser", async () => {
    const user = userEvent.setup();
    render(<LeadForm />);
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "cv.pdf", { type: "application/pdf" });
    await fill(user, big);
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("File is too large (max 5 MB)")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts multipart to the same-origin API and shows confirmation", async () => {
    fetchMock.mockResolvedValue(json(201, { id: "abc", message: "ok" }));
    const user = userEvent.setup();
    render(<LeadForm />);
    await fill(user, pdf);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByText("Thank you!")).toBeInTheDocument();
    const request = fetchMock.mock.calls[0]![0] as Request;
    expect(new URL(request.url).pathname).toBe("/api/v1/leads");
    expect(request.method).toBe("POST");
    expect(request.credentials).toBe("same-origin");
    const body = await request.formData();
    expect(body.get("firstName")).toBe("Ada");
    expect(body.get("email")).toBe("ada@example.com");
    expect(body.get("website")).toBe("");
    // (Vitest's Request shim drops the filename across .formData(); browsers keep it.)
    expect(await (body.get("resume") as Blob).text()).toBe("%PDF-1.4");
  });

  it("maps API field errors back onto the field", async () => {
    fetchMock.mockResolvedValue(
      json(415, { detail: [{ loc: ["body", "resume"], msg: "File contents don't match a PDF, DOC, or DOCX document" }] }),
    );
    const user = userEvent.setup();
    render(<LeadForm />);
    await fill(user, pdf);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByText("File contents don't match a PDF, DOC, or DOCX document")).toBeInTheDocument();
    expect(screen.queryByText("Thank you!")).not.toBeInTheDocument();
  });

  it("explains rate limiting", async () => {
    fetchMock.mockResolvedValue(json(429, { error: "Rate limit exceeded" }));
    const user = userEvent.setup();
    render(<LeadForm />);
    await fill(user, pdf);
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Too many attempts"));
  });

  it("shows a retryable error when the request cannot reach the API", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    render(<LeadForm />);
    await fill(user, pdf);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });
});
