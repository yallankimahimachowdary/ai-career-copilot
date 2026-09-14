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
      <div className="p-8 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No location demand data available for this query.
      </div>
    )
  }

  const chartData = locations.slice(0, 8).map((loc) => ({
    name: loc.location.replace(/, USA?$/, "").replace(/, United States$/, ""),
    count: loc.posting_count,
    percentage: loc.percentage,
    salary: loc.avg_annual_salary,
    remote: loc.remote_pct,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const d = payload[0].payload
      return (
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 shadow-xl text-xs space-y-1">
          <div className="font-bold text-white">{d.name}</div>
          <div className="text-blue-400 font-mono">
            {d.count} job postings ({d.percentage}%)
          </div>
          {d.salary && (
            <div className="text-emerald-400 font-mono">
              Avg Salary: {formatCurrency(d.salary)} / yr
            </div>
          )}
          <div className="text-slate-400">Remote Percentage: {d.remote}%</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      {/* Top Callout Banner */}
      {hottestMarket && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-xs">
          <div className="flex items-center gap-2 text-rose-300">
            <Flame className="h-4 w-4 text-rose-400 shrink-0" />
            <span>
              Highest Concentration Market: <strong className="text-white">{hottestMarket}</strong>
            </span>
          </div>
          <Badge variant="danger" className="text-[10px]">
            Hottest Hub
          </Badge>
        </div>
      )}

      {/* Location Volume Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <MapPin className="h-4 w-4 text-blue-400" />
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
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#cbd5e1", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                  width={100}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill="#3b82f6" radius={[0, 6, 6, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={index === 0 ? "#f43f5e" : index < 3 ? "#3b82f6" : "#6366f1"}
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
            className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white text-sm truncate">{loc.location}</span>
              <span className="text-xs font-mono text-blue-400 font-bold">{loc.percentage}%</span>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-800/60">
              <span>Avg: {formatCurrency(loc.avg_annual_salary)}</span>
              <span className="text-emerald-400">{loc.remote_pct}% Remote</span>
            </div>
          </div>
        ))}
      </div>

      {narrative && (
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300 leading-relaxed">
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
