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
      <div className="p-8 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
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
        <div className="p-3 rounded-xl bg-white border border-[#DDD6E7] shadow-lg text-xs space-y-1">
          <div className="font-bold text-[#3A3A52]">{d.name}</div>
          <div className="text-[#7A2D4A] font-mono font-semibold">
            {d.count} job postings ({d.percentage}%)
          </div>
          <div className="text-[#5C5C7A] capitalize">Demand Signal: {d.signal}</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      <Card className="border-[#DDD6E7] bg-white">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <Flame className="h-4 w-4 text-[#7A2D4A]" />
              Most In-Demand Skills & Technologies (Top 10)
            </CardTitle>
            <span className="text-xs font-mono text-[#5C5C7A]">
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
                  tick={{ fill: "#5C5C7A", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
                  unit="%"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#3A3A52", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
                  width={80}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="percentage" fill="#7A2D4A" radius={[0, 6, 6, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        index === 0
                          ? "#7A2D4A" // Burgundy top skill
                          : entry.signal === "high"
                          ? "#5C5C7A" // Slate primary
                          : "#8B8BA3" // Muted slate
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
              className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] flex items-center justify-between shadow-sm"
            >
              <div>
                <span className="text-sm font-semibold text-[#3A3A52] block">{s.skill}</span>
                <span className="text-xs text-[#5C5C7A] font-mono block">
                  {s.posting_count} postings ({s.percentage}%)
                </span>
                <div className="flex flex-col gap-0.5 pt-1 text-[11px] text-[#5C5C7A]">
                  <span>
                    Demand Share:{" "}
                    <strong className="text-[#3A3A52]">
                      {s.demand_share != null
                        ? `${(s.demand_share * (s.demand_share <= 1 ? 100 : 1)).toFixed(1)}%`
                        : "N/A"}
                    </strong>
                  </span>
                  <span>
                    Velocity:{" "}
                    <strong className="text-[#3A3A52]">
                      {s.velocity != null
                        ? `${s.velocity > 0 ? "+" : ""}${s.velocity}`
                        : "N/A (single baseline period)"}
                    </strong>
                  </span>
                </div>
              </div>
              <Badge variant={badge.variant} className="text-[10px]">
                {badge.label}
              </Badge>
            </div>
          )
        })}
      </div>

      {narrative && (
        <div className="p-4 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-xs text-[#3A3A52] leading-relaxed">
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
