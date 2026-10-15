// A barcode picture (Code 128, the kind every scanner reads) drawn from the code text.
import { useEffect, useRef } from "react";
import JsBarcode from "jsbarcode";

export default function Barcode({ value, height = 60, width = 2, showText = true }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !value) return;
    try {
      JsBarcode(ref.current, String(value), { format: "CODE128", height, width, displayValue: showText, fontSize: 16, margin: 6, background: "#ffffff" });
    } catch {
      /* a code with characters Code 128 cannot draw: leave the picture empty, the text is still shown elsewhere */
    }
  }, [value, height, width, showText]);
  return <svg ref={ref} role="img" aria-label={`Barcode ${value}`} className="max-w-full" />;
}
