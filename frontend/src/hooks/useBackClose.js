import { useEffect, useRef } from "react";

// The back button (Android hardware button, browser back, a swipe) closes the sheet, dialog or drawer that is open on top, before it leaves the page.
// Opening one adds a history entry; closing it by hand removes that entry again. Sheets stacked on each other close one at a time, the top one first.
const stack = [];
let counter = 0;

export default function useBackClose(open, onClose) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const id = ++counter;
    stack.push(id);
    window.history.pushState({ ...(window.history.state || {}), hwSheet: id }, "");
    const onPop = () => {
      if (stack[stack.length - 1] !== id) return;      // a sheet above this one answers first
      stack.pop();
      close.current?.();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      const at = stack.indexOf(id);
      if (at >= 0) stack.splice(at, 1);
      // closed by hand: take our history entry away again (checked a moment later, so a page change or a quick re-open is left alone)
      setTimeout(() => { if (window.history.state?.hwSheet === id) window.history.back(); }, 0);
    };
  }, [open]);
}
