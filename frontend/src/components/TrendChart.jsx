import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// points: [{date, value, reference_low, reference_high}] taken from the database.
export default function TrendChart({ points, unit, name }) {
  if (!points || points.length === 0) return null;
  const last = points[points.length - 1];
  const low = last.reference_low;
  const high = last.reference_high;
  const values = points.map((p) => p.value).concat([low, high].filter((v) => v !== null && v !== undefined));
  const pad = (Math.max(...values) - Math.min(...values)) * 0.2 || 1;

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={[Math.min(...values) - pad, Math.max(...values) + pad]} tick={{ fontSize: 12 }} tickFormatter={(v) => Number(v.toFixed(1))} />
          <Tooltip formatter={(v) => [`${v} ${unit || ""}`, name]} />
          {low != null && high != null && <ReferenceArea y1={low} y2={high} fill="#10b981" fillOpacity={0.1} label={{ value: "Reference range", fontSize: 11, fill: "#047857" }} />}
          {low != null && high == null && <ReferenceLine y={low} stroke="#10b981" strokeDasharray="4 4" label={{ value: `> ${low}`, fontSize: 11 }} />}
          {high != null && low == null && <ReferenceLine y={high} stroke="#10b981" strokeDasharray="4 4" label={{ value: `< ${high}`, fontSize: 11 }} />}
          <Line type="monotone" dataKey="value" stroke="#059669" strokeWidth={2.5} dot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
