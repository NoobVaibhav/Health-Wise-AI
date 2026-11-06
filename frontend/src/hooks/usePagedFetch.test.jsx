import { describe, expect, it, vi } from "vitest";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import usePagedFetch from "./usePagedFetch";
import ShowMore from "../components/ShowMore";

const rowsOf = (from, to) => Array.from({ length: to - from }, (_, i) => ({ id: from + i }));

describe("usePagedFetch", () => {
  it("loads the first page, then adds the next one", async () => {
    const fetchPage = vi.fn((offset) => Promise.resolve({ rows: offset === 0 ? rowsOf(0, 2) : rowsOf(2, 3), total: 3 }));
    const { result } = renderHook(() => usePagedFetch(fetchPage, []));
    await waitFor(() => expect(result.current.data?.length).toBe(2));
    expect(result.current.total).toBe(3);
    expect(result.current.hasMore).toBe(true);
    await act(async () => { await result.current.loadMore(); });
    expect(result.current.data.map((r) => r.id)).toEqual([0, 1, 2]);
    expect(fetchPage).toHaveBeenLastCalledWith(2);
    expect(result.current.hasMore).toBe(false);
  });

  it("starts again from the first page when the search changes, and ignores a late answer to the old search", async () => {
    let resolveOld;
    const fetchPage = vi.fn((offset, q) => (q === "old" ? new Promise((r) => { resolveOld = r; }) : Promise.resolve({ rows: rowsOf(10, 11), total: 1 })));
    const { result, rerender } = renderHook(({ q }) => usePagedFetch((offset) => fetchPage(offset, q), [q]), { initialProps: { q: "old" } });
    rerender({ q: "new" });
    await waitFor(() => expect(result.current.data?.map((r) => r.id)).toEqual([10]));
    await act(async () => { resolveOld({ rows: rowsOf(0, 5), total: 5 }); });
    expect(result.current.data.map((r) => r.id)).toEqual([10]);
    expect(result.current.total).toBe(1);
  });

  it("shows the error and keeps what was already loaded when the next page fails", async () => {
    const fetchPage = vi.fn((offset) => (offset === 0 ? Promise.resolve({ rows: rowsOf(0, 2), total: 4 }) : Promise.reject(new Error("offline"))));
    const { result } = renderHook(() => usePagedFetch(fetchPage, []));
    await waitFor(() => expect(result.current.data?.length).toBe(2));
    await act(async () => { await result.current.loadMore(); });
    expect(result.current.error).toBeTruthy();
    expect(result.current.data.length).toBe(2);
  });
});

describe("ShowMore", () => {
  it("says how many are shown and offers the next page only when there is one", async () => {
    const onMore = vi.fn();
    const { rerender } = render(<ShowMore shown={100} total={250} hasMore loading={false} onMore={onMore} noun="patients" />);
    expect(screen.getByText("Showing 100 of 250 patients")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(onMore).toHaveBeenCalledTimes(1);
    rerender(<ShowMore shown={250} total={250} hasMore={false} loading={false} onMore={onMore} noun="patients" />);
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
    rerender(<ShowMore shown={0} total={0} hasMore={false} loading={false} onMore={onMore} />);
    expect(screen.queryByText(/Showing/)).toBeNull();
  });
});
