import { describe, expect, it } from "vitest";
import main from "../../main.jsx?raw";
import app from "../../App.jsx?raw";

describe("a page that fails to draw", () => {
  it.fails("F-05: the application has an error boundary, so an unexpected server answer shows a message and a way out instead of a blank screen", () => {
    // Reproduced in a browser by tests/security_and_chaos/ui_chaos_playwright.py: 68 page and answer combinations end in a white screen.
    expect(main + app).toMatch(/ErrorBoundary|componentDidCatch|getDerivedStateFromError|errorElement/);
  });
});
