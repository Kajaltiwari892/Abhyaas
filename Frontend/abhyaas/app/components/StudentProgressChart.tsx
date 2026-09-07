"use client";

import { Sparkles, TrendingUp } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "./ThemeProvider";

type TrendPoint = { date: string; accuracy: number };

export default function StudentProgressChart({ trend }: { trend: TrendPoint[] }) {
  const { theme } = useTheme();
  const data = trend.slice(-12).map((point, index) => ({
    ...point,
    session: index + 1,
    label: new Date(point.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
  }));
  const first = data[0]?.accuracy ?? 0;
  const latest = data.at(-1)?.accuracy ?? 0;
  const change = Math.round((latest - first) * 10) / 10;
  const best = data.length ? Math.max(...data.map((point) => point.accuracy)) : 0;
  const tooltipBackground = theme === "light" ? "#fffdf7" : "#11160f";
  const tooltipText = theme === "light" ? "#283126" : "#edf1e9";

  return <div className="student-progress-chart">
    <div className="progress-chart-summary">
      <span><TrendingUp size={16} /><strong>{change >= 0 ? "+" : ""}{change}%</strong><small>change across recent sessions</small></span>
      <span><Sparkles size={16} /><strong>{best}%</strong><small>personal best</small></span>
    </div>
    <div className="progress-chart-canvas" role="img" aria-label="Animated chart of accuracy across recent completed study sessions">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 18, right: 18, left: -10, bottom: 4 }}>
          <defs>
            <linearGradient id="studentAccuracyArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#9caf58" stopOpacity={0.5} />
              <stop offset="95%" stopColor="#9caf58" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={theme === "light" ? "rgba(76,94,57,.13)" : "rgba(174,191,111,.12)"} strokeDasharray="4 6" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={22} tick={{ fill: theme === "light" ? "#6b7567" : "#7d887b", fontSize: 10 }} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickLine={false} axisLine={false} width={42} tick={{ fill: theme === "light" ? "#6b7567" : "#7d887b", fontSize: 10 }} tickFormatter={(value) => `${value}%`} />
          <Tooltip cursor={{ stroke: "rgba(144,163,80,.45)", strokeWidth: 1 }} contentStyle={{ background: tooltipBackground, border: "1px solid rgba(137,154,84,.34)", borderRadius: 10, color: tooltipText, boxShadow: "0 14px 35px rgba(30,40,24,.16)", fontSize: 11 }} labelFormatter={(value) => `Session completed ${value}`} formatter={(value) => [`${value}%`, "Accuracy"]} />
          <Area dataKey="accuracy" name="Accuracy" type="monotone" fill="url(#studentAccuracyArea)" stroke="#829747" strokeWidth={3} dot={{ r: 4, fill: tooltipBackground, stroke: "#829747", strokeWidth: 2 }} activeDot={{ r: 6, fill: "#c7db78", stroke: "#53632d", strokeWidth: 2 }} isAnimationActive animationDuration={1100} animationEasing="ease-out" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  </div>;
}
