import { describe, expect, it, vi, beforeEach } from "vitest";
import { useState } from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setViewport } from "../test/viewport";

let mockUser = { id: 2, role: "DOCTOR", full_name: "Dr. Anjali Sharma", permissions: [], grade: "CONSULTANT" };
vi.mock("../context/AuthContext", () => ({
  ROLE_HOME: { PATIENT: "/patient", DOCTOR: "/doctor", PHARMACY: "/pharmacy" },
  useAuth: () => ({ user: mockUser, loading: false, logout: vi.fn() }),
}));
vi.mock("./DataViews", () => ({ Avatar: () => <span /> }));
import Layout from "./Layout";
import ResponsiveTable from "./ResponsiveTable";
import SplitView from "./SplitView";
import PatientBanner from "./PatientBanner";
import ActionBar from "./ActionBar";
import Stepper from "./Stepper";
import BarcodeScan, { barcodeScanSupported } from "./BarcodeScan";
import { Modal } from "./ui";
import { flagFor } from "../pages/lab/ResultEntry";

const frame = (path = "/doctor") => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route element={<Layout />}><Route path="/doctor" element={<p>Doctor page</p>} /></Route></Routes>
  </MemoryRouter>,
);
beforeEach(() => { setViewport(1440); document.body.style.overflow = ""; });

describe("the staff frame follows the width of the window", () => {
  it("phone: a hamburger and a drawer, no rail", () => {
    setViewport(390);
    frame();
    expect(screen.queryByRole("button", { name: "Open the full menu" })).toBeNull();
    expect(screen.getByRole("button", { name: "Open menu" })).toBeTruthy();
    expect(document.querySelector("aside").hasAttribute("inert")).toBe(true);
  });

  it("tablet (portrait and landscape): an icon rail with a named link for every page; the full menu opens over the page from its top button", async () => {
    for (const width of [768, 820, 1024, 1180]) {
      setViewport(width);
      const { unmount } = frame();
      const rail = document.querySelector("[data-rail]");
      expect(rail, `rail at ${width}`).toBeTruthy();
      expect(within(rail).getByRole("link", { name: "Today's Queue" })).toBeTruthy();       // icons are named for screen readers and tooltips
      expect(within(rail).getByRole("link", { name: "Dashboard" }).getAttribute("aria-current")).toBe("page");
      expect(screen.queryByRole("button", { name: "Open menu" })).toBeTruthy();             // present in the DOM but hidden from 640 px by the sm:hidden class
      await userEvent.click(within(rail).getByRole("button", { name: "Open the full menu" }));
      expect(screen.getByRole("dialog", { name: "Menu" })).toBeTruthy();
      await userEvent.keyboard("{Escape}");
      expect(screen.queryByRole("dialog", { name: "Menu" })).toBeNull();
      unmount();
    }
  });

  it("desktop (1280 px and up): the full sidebar, no rail, no drawer", () => {
    setViewport(1440);
    frame();
    expect(document.querySelector("[data-rail]")).toBeNull();
    const aside = document.querySelector("aside");
    expect(aside.hasAttribute("inert")).toBe(false);
    expect(aside.getAttribute("role")).toBeNull();
  });

  it("the patient frame is unchanged: still a drawer below 1024 px and no rail", () => {
    mockUser = { id: 1, role: "PATIENT", full_name: "Rahul Patil", permissions: [] };
    setViewport(900);
    frame("/patient");
    expect(document.querySelector("[data-rail]")).toBeNull();
    mockUser = { id: 2, role: "DOCTOR", full_name: "Dr. Anjali Sharma", permissions: [], grade: "CONSULTANT" };
  });
});

const columns = [
  { key: "name", label: "Medicine", priority: 1 },
  { key: "qty", label: "Quantity", priority: 2, numeric: true },
  { key: "batch", label: "Batch", priority: 3 },
];
const rows = [{ id: 1, name: "Tab. Aspirin", qty: 12, batch: "B-1" }, { id: 2, name: "Inj. Ceftriaxone", qty: 3, batch: "B-2" }];

describe("ResponsiveTable", () => {
  it("phone: every row is a card with all its values, and no table", () => {
    setViewport(390);
    const { container } = render(<ResponsiveTable columns={columns} rows={rows} caption="Stock" />);
    expect(container.querySelector("table")).toBeNull();
    const cards = container.querySelectorAll("li[data-row]");
    expect(cards).toHaveLength(2);
    expect(cards[0].textContent).toMatch(/Medicine.*Tab. Aspirin.*Quantity.*12.*Batch.*B-1/);
  });

  it("tablet portrait: priority 1 and 2 columns show, the rest opens under the row", async () => {
    setViewport(768);
    const { container } = render(<ResponsiveTable columns={columns} rows={rows} caption="Stock" />);
    const heads = [...container.querySelectorAll("thead th")].map((h) => h.textContent);
    expect(heads).toContain("Medicine");
    expect(heads).toContain("Quantity");
    expect(heads).not.toContain("Batch");
    expect(container.querySelector("[data-details]")).toBeNull();
    const toggle = screen.getAllByRole("button", { name: "Show details" })[0];
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(toggle);
    expect(container.querySelector("[data-details]").textContent).toMatch(/Batch:\s*B-1/);
    expect(screen.getAllByRole("button", { name: "Hide details" })[0].getAttribute("aria-expanded")).toBe("true");
  });

  it("landscape and desktop: every column, a sticky header, tabular numbers", () => {
    setViewport(1180);
    const { container } = render(<ResponsiveTable columns={columns} rows={rows} caption="Stock" />);
    expect([...container.querySelectorAll("thead th")].map((h) => h.textContent)).toEqual(["Medicine", "Quantity", "Batch"]);
    expect(container.querySelector("thead th").className).toMatch(/sticky top-0/);
    expect(container.querySelector("td.num")).toBeTruthy();
  });

  it("shows a skeleton while loading, an empty state with no rows, and 'Show more' pages a long list", async () => {
    setViewport(1440);
    const { rerender } = render(<ResponsiveTable columns={columns} rows={[]} loading />);
    expect(screen.getByRole("status").textContent).toBe("Loading...");
    rerender(<ResponsiveTable columns={columns} rows={[]} empty="No stock yet." />);
    expect(screen.getByText("No stock yet.")).toBeTruthy();
    const many = Array.from({ length: 60 }, (_, i) => ({ id: i, name: `Item ${i}`, qty: i, batch: "x" }));
    const { container } = render(<ResponsiveTable columns={columns} rows={many} pageSize={25} />);
    expect(container.querySelectorAll("tbody tr[data-row]")).toHaveLength(25);
    await userEvent.click(screen.getByRole("button", { name: /Show more \(35 left\)/ }));
    expect(container.querySelectorAll("tbody tr[data-row]")).toHaveLength(50);
  });
});

describe("SplitView (master-detail)", () => {
  const list = <p>The list</p>;
  const detail = <p>The detail</p>;
  it("landscape: the list and the detail side by side", () => {
    setViewport(1180);
    const { container } = render(<SplitView list={list} detail={detail} hasSelection />);
    expect(container.querySelector("[data-split]")).toBeTruthy();
    expect(screen.getByText("The list")).toBeTruthy();
    expect(screen.getByText("The detail")).toBeTruthy();
  });
  it("landscape with nothing chosen shows the empty detail text", () => {
    setViewport(1180);
    render(<SplitView list={list} detail={detail} hasSelection={false} emptyDetail={<p>Choose a patient</p>} />);
    expect(screen.getByText("Choose a patient")).toBeTruthy();
  });
  it("portrait: one pane at a time, with a Back button from the detail to the list", async () => {
    setViewport(800);
    const onBack = vi.fn();
    const { rerender } = render(<SplitView list={list} detail={detail} hasSelection={false} onBack={onBack} />);
    expect(screen.getByText("The list")).toBeTruthy();
    expect(screen.queryByText("The detail")).toBeNull();
    rerender(<SplitView list={list} detail={detail} hasSelection onBack={onBack} />);
    expect(screen.queryByText("The list")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Back to the list/ }));
    expect(onBack).toHaveBeenCalled();
  });
});

describe("PatientBanner, ActionBar, Stepper", () => {
  it("the banner stays under the top bar and shows the allergies in a red alert", () => {
    const { container } = render(<PatientBanner name="Pranav Sathe" uhid="HW-26-000002" age={22} gender="male" allergies="Penicillin" />);
    expect(container.querySelector("[data-patient-banner]").className).toMatch(/sticky top-/);
    expect(screen.getByRole("alert").textContent).toMatch(/Allergies: Penicillin/);
    expect(screen.getByRole("alert").className).toMatch(/bg-red-100/);
    expect(screen.getByText(/HW-26-000002 · 22 y · male/)).toBeTruthy();
  });
  it("without allergies it says so instead of showing an alert", () => {
    render(<PatientBanner name="A" uhid="U" />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("No allergies recorded")).toBeTruthy();
  });
  it("the action bar sticks to the bottom, above the home indicator, with the status on the left", () => {
    const { container } = render(<ActionBar status={<span>Saved</span>}><button>Save draft</button></ActionBar>);
    const bar = container.querySelector("[data-action-bar]");
    expect(bar.className).toMatch(/sticky bottom-0/);
    expect(bar.className).toMatch(/safe-bottom/);
    expect(within(bar).getByText("Saved")).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Save draft" })).toBeTruthy();
  });
  it("the stepper adds, subtracts, stays inside its limits and still accepts typing", async () => {
    const Host = () => { const [v, setV] = useState("2"); return <Stepper label="Quantity" value={v} onChange={setV} min={1} max={3} />; };
    render(<Host />);
    const box = screen.getByRole("textbox", { name: "Quantity" });
    await userEvent.click(screen.getByRole("button", { name: "More: Quantity" }));
    expect(box.value).toBe("3");
    expect(screen.getByRole("button", { name: "More: Quantity" }).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Less: Quantity" }));
    await userEvent.click(screen.getByRole("button", { name: "Less: Quantity" }));
    expect(box.value).toBe("1");
    expect(screen.getByRole("button", { name: "Less: Quantity" }).disabled).toBe(true);
    await userEvent.clear(box); await userEvent.type(box, "9"); await userEvent.tab();
    expect(box.value).toBe("3");                                  // typed 9, the limit is 3
  });
});

describe("the back button closes the sheet on top first", () => {
  const Sheet = ({ onClose, title = "Sheet" }) => <Modal title={title} onClose={onClose}><p>{title} body</p></Modal>;
  it("opening a sheet adds a history entry; the back button (popstate) closes it", async () => {
    const onClose = vi.fn();
    render(<Sheet onClose={onClose} />);
    expect(window.history.state?.hwSheet).toBeTruthy();
    act(() => { window.dispatchEvent(new PopStateEvent("popstate")); });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
  it("two sheets on top of each other close one at a time, the top one first", () => {
    const first = vi.fn(), second = vi.fn();
    render(<><Sheet onClose={first} title="Under" /><Sheet onClose={second} title="Over" /></>);
    act(() => { window.dispatchEvent(new PopStateEvent("popstate")); });
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });
  it("closing by hand takes the history entry away again", async () => {
    const { unmount } = render(<Sheet onClose={() => {}} />);
    const spy = vi.spyOn(window.history, "back").mockImplementation(() => {});
    unmount();
    await waitFor(() => expect(spy).toHaveBeenCalled());
    spy.mockRestore();
  });
});

describe("camera barcode scan", () => {
  const original = { detector: window.BarcodeDetector, media: navigator.mediaDevices };
  it("without BarcodeDetector the button is not shown (the typed or wedge-scanned box stays the way)", () => {
    delete window.BarcodeDetector;
    expect(barcodeScanSupported()).toBe(false);
    const { container } = render(<BarcodeScan onDetect={() => {}} />);
    expect(container.textContent).toBe("");
  });
  it("with the camera and the detector it opens the scanner, reads a code, closes, and stops the camera", async () => {
    const stop = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [{ stop }] })) } });
    window.BarcodeDetector = class { detect() { return Promise.resolve([{ rawValue: "HW00000004" }]); } };
    window.HTMLMediaElement.prototype.play = () => Promise.resolve();
    const onDetect = vi.fn();
    render(<BarcodeScan onDetect={onDetect} />);
    await userEvent.click(screen.getByRole("button", { name: /Scan with camera/ }));
    await waitFor(() => expect(onDetect).toHaveBeenCalledWith("HW00000004"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(stop).toHaveBeenCalled();
    delete window.BarcodeDetector;
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: original.media });
  });
  it("a camera that cannot be opened shows a message and leaves typing available", async () => {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn(() => Promise.reject(new Error("denied"))) } });
    window.BarcodeDetector = class { detect() { return Promise.resolve([]); } };
    render(<BarcodeScan onDetect={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /Scan with camera/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/camera could not be opened/i);
    delete window.BarcodeDetector;
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: original.media });
  });
});

describe("lab result entry: the live flag next to a typed value", () => {
  const a = { ref_low: 4, ref_high: 11, critical_low: 2, critical_high: 20 };
  it("flags low, normal, high and critical values and says nothing for an empty or non-numeric entry", () => {
    expect(flagFor("7.5", a).key).toBe("normal");
    expect(flagFor("3.1", a).key).toBe("low");
    expect(flagFor("12", a).key).toBe("high");
    expect(flagFor("1.5", a)).toMatchObject({ key: "critical", label: "Critical low" });
    expect(flagFor("25", a)).toMatchObject({ key: "critical", label: "Critical high" });
    expect(flagFor("", a)).toBeNull();
    expect(flagFor("abc", a)).toBeNull();
    expect(flagFor("7,5", a).key).toBe("normal");                // a decimal comma
    expect(flagFor("7", { ref_low: null, ref_high: null })).toBeNull();   // no range set by the hospital: nothing is guessed
  });
});
