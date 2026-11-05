import useMediaQuery from "./useMediaQuery";

// The four layout modes, written down once (widths of the window, so split-screen and rotation are followed, never the device):
//   phone          under 640 px     one column, drawer menu, tables as cards
//   tabletPortrait 640 - 1023 px    icon rail, two columns where it fits
//   tabletLandscape 1024 - 1279 px  icon rail, split views (list left, detail right)
//   desktop        1280 px and up   full sidebar
export const BREAKPOINTS = { tablet: 640, landscape: 1024, desktop: 1280 };

export default function useLayoutMode() {
  const tablet = useMediaQuery(`(min-width: ${BREAKPOINTS.tablet}px)`);
  const landscape = useMediaQuery(`(min-width: ${BREAKPOINTS.landscape}px)`);
  const desktop = useMediaQuery(`(min-width: ${BREAKPOINTS.desktop}px)`);
  const mode = desktop ? "desktop" : landscape ? "tabletLandscape" : tablet ? "tabletPortrait" : "phone";
  return { mode, phone: mode === "phone", split: landscape, rail: tablet && !desktop, desktop };
}
