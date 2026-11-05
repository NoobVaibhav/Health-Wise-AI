// In the Android app the hardware back button goes back one step in the page history (which also closes an open sheet, see useBackClose).
// At the first page it sends the app to the background instead of closing it in the middle of something.
import { Capacitor } from "@capacitor/core";

export async function startNativeBack() {
  if (!Capacitor.isNativePlatform()) return;
  const { App } = await import("@capacitor/app");
  await App.addListener("backButton", ({ canGoBack }) => {
    if (canGoBack || window.history.length > 1) window.history.back();
    else App.minimizeApp?.();
  });
}
