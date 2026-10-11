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
import { MapPin, Globe, Sparkles, Building, Flame } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatCurrency } from "@/lib/utils"

export function DemandHeatmap({ locations = [], hottestMarket, narrative }) {
  if (!locations || locations.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
        No location demand data available for this query.
      </div>
    )
  }

  const chartData = locations.slice(0, 8).map((loc) => ({
    name: loc.location.replace(/, (?:India|IN|USA?|United States)$/i, "").trim(),
    count: loc.posting_count,
    percentage: loc.percentage,
    salary: loc.avg_annual_salary,
    remote: loc.remote_pct,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload
      return (
        <div className="p-3 rounded-xl bg-white border border-[#DDD6E7] shadow-lg text-xs space-y-1">
          <div className="font-bold text-[#3A3A52]">{d.name}</div>
          <div className="text-[#7A2D4A] font-mono">
            {d.count} job postings ({d.percentage}%)
          </div>
          {d.salary && (
            <div className="text-emerald-800 font-mono">
              Avg Salary: {formatCurrency(d.salary)} / yr
            </div>
          )}
          <div className="text-[#5C5C7A]">Remote Percentage: {d.remote}%</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      {/* Top Callout Banner */}
      {hottestMarket && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-xs">
          <div className="flex items-center gap-2 text-[#7A2D4A]">
            <Flame className="h-4 w-4 text-[#7A2D4A] shrink-0" />
            <span>
              Highest Concentration Market: <strong className="text-[#3A3A52]">{hottestMarket}</strong>
            </span>
          </div>
          <Badge variant="primary" className="text-[10px]">
            Hottest Hub
          </Badge>
        </div>
      )}

      {/* Location Volume Chart */}
      <Card className="border-[#DDD6E7] bg-white">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <MapPin className="h-4 w-4 text-[#7A2D4A]" />
              Geographic Concentration of Opportunities
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 10, right: 30, left: 100, bottom: 5 }}
              >
                <XAxis
                  type="number"
                  tick={{ fill: "#5C5C7A", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#3A3A52", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
                  width={100}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill="#7A2D4A" radius={[0, 6, 6, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index === 0 ? "#7A2D4A" : index < 3 ? "#5C5C7A" : "#8B8BA3"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Location Details Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {locations.slice(0, 6).map((loc, idx) => (
          <div
            key={idx}
            className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] space-y-2 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[#3A3A52] text-sm truncate">{loc.location}</span>
              <span className="text-xs font-mono text-[#7A2D4A] font-bold">{loc.percentage}%</span>
            </div>
            <div className="flex items-center justify-between text-xs text-[#5C5C7A] pt-1 border-t border-[#DDD6E7]">
              <span>Avg: {formatCurrency(loc.avg_annual_salary)}</span>
              <span className="text-emerald-700 font-medium">{loc.remote_pct}% Remote</span>
            </div>
          </div>
        ))}
      </div>

      {narrative && (
        <div className="p-4 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-xs text-[#3A3A52] leading-relaxed">
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
