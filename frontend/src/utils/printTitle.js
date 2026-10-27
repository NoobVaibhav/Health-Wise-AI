// "Save as PDF" in the browser names the file after the page title, which is always "HealthWise AI".
// printAs() gives the page a proper title for the print window, for example "Rahul_Patil_Medical_History", and puts the old title back afterwards.

/** "Rahul Patil" -> "Rahul_Patil". Letters (also Hindi and Marathi) and numbers stay; everything else becomes one underscore. */
export const fileSafe = (text) => String(text ?? "").replace(/[^\p{L}\p{M}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "")
  .replace(/(^|_)(\p{Ll})/gu, (_, start, letter) => start + letter.toUpperCase());         // each word starts with a capital letter

/** The file name: the parts joined with underscores, e.g. fileName("Rahul Patil", "Medical history") = "Rahul_Patil_Medical_History". */
export const fileName = (...parts) => parts.map(fileSafe).filter(Boolean).join("_");

export function printAs(...parts) {
  const title = fileName(...parts);
  if (!title) { window.print(); return; }
  const before = document.title;
  const restore = () => { document.title = before; window.removeEventListener("afterprint", restore); };
  document.title = title;
  window.addEventListener("afterprint", restore);
  window.print();
}
