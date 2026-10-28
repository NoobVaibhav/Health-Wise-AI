// The "In short" summary as points: [{ text, items? }]. The server sends them (insights.summary_points); a summary written another way
// (for example by an AI model) is split into its sentences so it is still shown as points.
export function summaryPoints(report) {
  const sent = report.insights?.summary_points;
  if (sent?.length) return sent;
  const text = String(report.ai_summary || "").trim();
  if (!text) return [];
  return text.split(/(?<=[.!?])\s+(?=[A-Z0-9"'(])/).map((s) => ({ text: s.trim() })).filter((p) => p.text);
}
