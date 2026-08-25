"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const previewData = [
  { session: 1, english: 54, generalKnowledge: 42 }, { session: 2, english: 58, generalKnowledge: 46 },
  { session: 3, english: 55, generalKnowledge: 49 }, { session: 4, english: 62, generalKnowledge: 47 },
  { session: 5, english: 65, generalKnowledge: 53 }, { session: 6, english: 63, generalKnowledge: 57 },
  { session: 7, english: 68, generalKnowledge: 55 }, { session: 8, english: 71, generalKnowledge: 61 },
  { session: 9, english: 69, generalKnowledge: 64 }, { session: 10, english: 74, generalKnowledge: 62 },
  { session: 11, english: 76, generalKnowledge: 67 }, { session: 12, english: 73, generalKnowledge: 70 },
  { session: 13, english: 79, generalKnowledge: 68 }, { session: 14, english: 81, generalKnowledge: 73 },
  { session: 15, english: 78, generalKnowledge: 75 }, { session: 16, english: 82, generalKnowledge: 72 },
  { session: 17, english: 84, generalKnowledge: 77 }, { session: 18, english: 81, generalKnowledge: 79 },
  { session: 19, english: 86, generalKnowledge: 76 }, { session: 20, english: 84, generalKnowledge: 81 },
  { session: 21, english: 87, generalKnowledge: 83 }, { session: 22, english: 89, generalKnowledge: 80 },
  { session: 23, english: 86, generalKnowledge: 84 }, { session: 24, english: 90, generalKnowledge: 82 },
  { session: 25, english: 91, generalKnowledge: 86 }, { session: 26, english: 89, generalKnowledge: 87 },
  { session: 27, english: 92, generalKnowledge: 85 }, { session: 28, english: 91, generalKnowledge: 89 },
  { session: 29, english: 94, generalKnowledge: 88 }, { session: 30, english: 93, generalKnowledge: 91 },
];

export default function ProgressAreaChart() {
  const [range, setRange] = useState("14");
  const data = previewData.slice(-Number(range));

  return (
    <div className="cds-chart-card">
      <header>
        <div><span>Accuracy trajectory</span><small>Practice session vs accuracy percentage</small></div>
        <div className="cds-chart-controls"><label><span>Range</span><select value={range} onChange={(event) => setRange(event.target.value)}><option value="7">7 sessions</option><option value="14">14 sessions</option><option value="30">30 sessions</option></select></label></div>
      </header>
      <div className="cds-chart-wrap" role="img" aria-label="Illustrative preview of a CDS accuracy chart with practice sessions on the horizontal axis and accuracy percentage on the vertical axis">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 12, right: 16, left: -8, bottom: 4 }}>
            <defs>
              <linearGradient id="englishArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#b9c878" stopOpacity={0.48} /><stop offset="95%" stopColor="#b9c878" stopOpacity={0.03} /></linearGradient>
              <linearGradient id="gkArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#d3ad58" stopOpacity={0.38} /><stop offset="95%" stopColor="#d3ad58" stopOpacity={0.02} /></linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="rgba(166,182,105,.12)" />
            <XAxis dataKey="session" tickLine={false} axisLine={false} minTickGap={26} tick={{ fill: "#7e887b", fontSize: 9 }} tickFormatter={(value) => `S${value}`} label={{ value: "PRACTICE SESSION", position: "insideBottom", offset: -2, fill: "#60695f", fontSize: 8 }} />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickLine={false} axisLine={false} tick={{ fill: "#7e887b", fontSize: 9 }} tickFormatter={(value) => `${value}%`} label={{ value: "ACCURACY", angle: -90, position: "insideLeft", fill: "#60695f", fontSize: 8 }} />
            <Tooltip cursor={{ stroke: "rgba(203,218,145,.22)" }} contentStyle={{ background: "#11150f", border: "1px solid rgba(177,192,122,.3)", color: "#edf0e8", fontSize: 10 }} labelFormatter={(value) => `Practice session ${value}`} formatter={(value, name) => [`${value}%`, name === "english" ? "English" : "General Knowledge"]} />
            <Legend iconType="circle" iconSize={7} wrapperStyle={{ color: "#a5afa4", fontSize: 9, paddingTop: 8 }} formatter={(value) => value === "english" ? "English" : "General Knowledge"} />
            <Area dataKey="generalKnowledge" type="natural" fill="url(#gkArea)" stroke="#d3ad58" strokeWidth={1.8} />
            <Area dataKey="english" type="natural" fill="url(#englishArea)" stroke="#b9c878" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
