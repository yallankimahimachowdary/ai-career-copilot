import React from "react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts"
import { Sparkles, TrendingUp, Flame } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export function TrendingSkills({ skills = [], totalPostings = 0, narrative }) {
  if (!skills || skills.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No skill demand trends found for this query.
      </div>
    )
  }

  const chartData = skills.slice(0, 10).map((s) => ({
    name: s.skill,
    count: s.posting_count,
    percentage: s.percentage,
    signal: s.trend_signal || "high",
  }))

  const getSignalBadge = (sig) => {
    switch (sig?.toLowerCase()) {
      case "high":
        return { label: "High Demand", variant: "danger" }
      case "moderate":
        return { label: "Steady", variant: "warning" }
      default:
        return { label: "Niche", variant: "default" }
    }
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload
      return (
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 shadow-xl text-xs space-y-1">
          <div className="font-bold text-white">{d.name}</div>
          <div className="text-blue-400 font-mono">
            {d.count} job postings ({d.percentage}%)
          </div>
          <div className="text-slate-400 capitalize">Demand Signal: {d.signal}</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Flame className="h-4 w-4 text-rose-400" />
              Most In-Demand Skills & Technologies (Top 10)
            </CardTitle>
            <span className="text-xs font-mono text-slate-400">
              Aggregated across {totalPostings || "all"} postings
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 10, right: 30, left: 80, bottom: 5 }}
              >
                <XAxis
                  type="number"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                  unit="%"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#cbd5e1", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                  width={80}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="percentage" fill="#3b82f6" radius={[0, 6, 6, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.signal === "high"
                          ? "#3b82f6"
                          : entry.signal === "moderate"
                          ? "#8b5cf6"
                          : "#64748b"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Skills breakdown chip cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {skills.slice(0, 9).map((s, idx) => {
          const badge = getSignalBadge(s.trend_signal)
          return (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between"
            >
              <div>
                <span className="text-sm font-semibold text-white block">{s.skill}</span>
                <span className="text-xs text-slate-400 font-mono">
                  {s.posting_count} postings ({s.percentage}%)
                </span>
              </div>
              <Badge variant={badge.variant} className="text-[10px]">
                {badge.label}
              </Badge>
            </div>
          )
        })}
      </div>

      {narrative && (
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300 leading-relaxed">
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
