import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MarkReachedOutButton } from "./MarkReachedOutButton";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => vi.stubGlobal("fetch", fetchMock));
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  refresh.mockReset();
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("MarkReachedOutButton", () => {
  it("sends a JSON PATCH and shows the new state", async () => {
    fetchMock.mockResolvedValue(json(200, { state: "REACHED_OUT" }));
    const user = userEvent.setup();
    render(<MarkReachedOutButton leadId="lead-1" initialState="PENDING" />);
    await user.click(screen.getByRole("button", { name: "Mark as reached out" }));

    expect(await screen.findByText("Reached out")).toBeInTheDocument();
    const request = fetchMock.mock.calls[0]![0] as Request;
    expect(request.method).toBe("PATCH");
    expect(new URL(request.url).pathname).toBe("/api/v1/leads/lead-1");
    expect(request.headers.get("content-type")).toContain("application/json");
    expect(await request.json()).toEqual({ state: "REACHED_OUT" });
    expect(refresh).toHaveBeenCalled();
  });

  it("is optimistic while the request is in flight", async () => {
    const pending = deferred<Response>();
    fetchMock.mockReturnValue(pending.promise);
    const user = userEvent.setup();
    render(<MarkReachedOutButton leadId="lead-1" initialState="PENDING" />);
    await user.click(screen.getByRole("button", { name: "Mark as reached out" }));

    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    pending.resolve(json(200, {}));
    expect(await screen.findByText("Reached out")).toBeInTheDocument();
  });

  it("shows the reached out state on 409 and explains why", async () => {
    fetchMock.mockResolvedValue(json(409, { detail: "Lead cannot move to that state" }));
    const user = userEvent.setup();
    render(<MarkReachedOutButton leadId="lead-1" initialState="PENDING" />);
    await user.click(screen.getByRole("button", { name: "Mark as reached out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already updated by someone else");
    expect(screen.getByText("Reached out")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark as reached out" })).not.toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
  });

  it("rolls back on other 4xx", async () => {
    fetchMock.mockResolvedValue(json(422, { detail: "nope" }));
    const user = userEvent.setup();
    render(<MarkReachedOutButton leadId="lead-1" initialState="PENDING" />);
    await user.click(screen.getByRole("button", { name: "Mark as reached out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't update the lead");
    expect(screen.getByRole("button", { name: "Mark as reached out" })).toBeInTheDocument();
  });

  it("rolls back and allows retry after a network failure", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    render(<MarkReachedOutButton leadId="lead-1" initialState="PENDING" />);
    await user.click(screen.getByRole("button", { name: "Mark as reached out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
    expect(screen.getByRole("button", { name: "Mark as reached out" })).toBeEnabled();
    expect(refresh).not.toHaveBeenCalled();
  });
});
