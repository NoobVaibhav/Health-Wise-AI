// Opens a clean page with a bill or a receipt and the print dialog. Everything that comes from the server is escaped first.
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const STYLE = "body{font-family:Arial,sans-serif;margin:24px;color:#111}h1{font-size:20px;margin:0}h2{font-size:15px;margin:16px 0 6px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #ddd;padding:6px;text-align:left}td.n,th.n{text-align:right}.muted{color:#555;font-size:12px}.tot td{font-weight:bold}";

function open(title, body) {
  const w = window.open("", "_blank", "noopener,width=800,height=900");
  if (!w) return false;
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>${STYLE}</style></head><body>${body}</body></html>`);
  w.document.close();
  w.focus();
  w.print();
  return true;
}

const head = (h) => `<h1>${esc(h?.name || "Hospital")}</h1><p class="muted">${esc(h?.address || "")} ${esc(h?.phone || "")}${h?.gst_number ? ` &middot; GSTIN ${esc(h.gst_number)}` : ""}</p>`;

export function printReceipt(r) {
  return open(`Receipt ${r.receipt_number}`, `${head(r.hospital)}<h2>Payment receipt ${esc(r.receipt_number)}</h2>
    <p>Received from <b>${esc(r.patient_name)}</b> (${esc(r.patient_code)}) on ${esc(new Date(r.received_at + "Z").toLocaleString())}</p>
    <table><tr><td>Invoice</td><td>${esc(r.invoice_number)}</td></tr><tr><td>Invoice total</td><td class="n">${money(r.invoice_total)}</td></tr>
    <tr><td>Method</td><td>${esc(r.method)}${r.reference ? ` (${esc(r.reference)})` : ""}</td></tr>
    <tr class="tot"><td>Amount received</td><td class="n">${money(r.amount)}</td></tr><tr><td>Balance after this payment</td><td class="n">${money(r.balance_after)}</td></tr></table>
    <p class="muted">Received by ${esc(r.received_by)}. This is a computer-generated receipt.</p>`);
}

export function printInvoice(inv, hospital) {
  const rows = inv.lines.map((l) => `<tr><td>${esc(l.description)}</td><td class="n">${l.quantity}</td><td class="n">${money(l.unit_price)}</td><td class="n">${esc(l.gst_percent)}%</td><td class="n">${money(l.amount + l.tax)}</td></tr>`).join("");
  return open(`Invoice ${inv.number || "draft"}`, `${head(hospital)}<h2>Invoice ${esc(inv.number || "(draft)")}</h2>
    <p><b>${esc(inv.patient_name)}</b> (${esc(inv.patient_code)})</p>
    <table><thead><tr><th>Item</th><th class="n">Qty</th><th class="n">Price</th><th class="n">GST</th><th class="n">Amount</th></tr></thead><tbody>${rows}</tbody></table>
    <table style="margin-top:10px"><tr><td>Subtotal</td><td class="n">${money(inv.subtotal)}</td></tr><tr><td>GST</td><td class="n">${money(inv.tax)}</td></tr>
    ${inv.discount ? `<tr><td>Discount (${esc(inv.discount_reason || "")})</td><td class="n">- ${money(inv.discount)}</td></tr>` : ""}
    <tr class="tot"><td>Total</td><td class="n">${money(inv.total)}</td></tr><tr><td>Paid</td><td class="n">${money(inv.paid)}</td></tr>
    ${inv.insurer_approved ? `<tr><td>Approved by insurer</td><td class="n">${money(inv.insurer_approved)}</td></tr><tr><td>Patient pays</td><td class="n">${money(inv.patient_payable)}</td></tr>` : ""}
    <tr class="tot"><td>Balance</td><td class="n">${money(inv.balance)}</td></tr></table>
    <p class="muted">Computer-generated invoice.</p>`);
}
