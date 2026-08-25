"use client";

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function OrdersChart({ data }: { data: { date: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <XAxis
          dataKey="date"
          tickFormatter={(value: string) => value.slice(5)}
          tick={{ fontSize: 12 }}
        />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={30} />
        <Tooltip />
        <Bar dataKey="count" fill="hsl(var(--primary))" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
