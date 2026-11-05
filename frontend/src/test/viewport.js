// Tests of the layout modes: pretend the window has a given width. Every (min-width / max-width) media query the code asks about answers for that width.
export function setViewport(width) {
  window.innerWidth = width;
  window.matchMedia = (query) => {
    const min = /min-width:\s*(\d+)px/.exec(query);
    const max = /max-width:\s*(\d+)px/.exec(query);
    const matches = (!min || width >= Number(min[1])) && (!max || width <= Number(max[1]));
    return { matches, media: query, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
  };
}
