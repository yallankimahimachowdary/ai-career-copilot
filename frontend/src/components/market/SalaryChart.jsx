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
import { DollarSign, Building, TrendingUp, Info } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { formatCurrency } from "@/lib/utils"

export function SalaryChart({ salaryBand, topPayingCompanies = [], narrative }) {
  if (!salaryBand || !salaryBand.median_annual) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No salary compensation data available for this query.
      </div>
    )
  }

  // Distribution percentiles data
  const percentileData = [
    { label: "Min Floor", value: salaryBand.min_annual, color: "#64748b" },
    { label: "25th Pct", value: salaryBand.p25_annual, color: "#38bdf8" },
    { label: "Median (50th)", value: salaryBand.median_annual, color: "#3b82f6" },
    { label: "75th Pct", value: salaryBand.p75_annual, color: "#6366f1" },
    { label: "Top Ceiling", value: salaryBand.max_annual, color: "#10b981" },
  ]

  // Top paying companies bar chart
  const companyData = topPayingCompanies.slice(0, 5).map((comp) => ({
    name: comp.company_name,
    salary: comp.median_salary || 0,
    count: comp.posting_count,
  }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 shadow-xl text-xs space-y-1">
          <div className="font-bold text-white">{data.label || data.name}</div>
          <div className="text-emerald-400 font-mono font-semibold">
            {formatCurrency(data.value || data.salary)} / yr
          </div>
          {data.count && (
            <div className="text-[10px] text-slate-400">Postings analyzed: {data.count}</div>
          )}
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-6">
      {/* 5-Number Summary Percentile Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
          <span className="text-[11px] text-slate-400 block font-medium">Minimum Floor</span>
          <span className="text-base font-bold text-slate-300 font-mono">
            {formatCurrency(salaryBand.min_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
          <span className="text-[11px] text-slate-400 block font-medium">25th Percentile</span>
          <span className="text-base font-bold text-sky-400 font-mono">
            {formatCurrency(salaryBand.p25_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-blue-600/15 border border-blue-500/40 text-center shadow-lg shadow-blue-950/40">
          <span className="text-[11px] text-blue-300 block font-semibold">Median Market</span>
          <span className="text-lg font-bold text-blue-400 font-mono">
            {formatCurrency(salaryBand.median_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
          <span className="text-[11px] text-slate-400 block font-medium">75th Percentile</span>
          <span className="text-base font-bold text-indigo-400 font-mono">
            {formatCurrency(salaryBand.p75_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-center">
          <span className="text-[11px] text-slate-400 block font-medium">Top Ceiling</span>
          <span className="text-base font-bold text-emerald-400 font-mono">
            {formatCurrency(salaryBand.max_annual)}
          </span>
        </div>
      </div>

      {/* Percentiles Bar Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-emerald-400" />
              Annual Compensation Benchmark Spectrum
            </CardTitle>
            <span className="text-xs font-mono text-slate-400">
              Sample: {salaryBand.sample_size || 0} postings
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-60 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={percentileData} margin={{ top: 10, right: 20, left: 20, bottom: 20 }}>
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                />
                <YAxis
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                  tickFormatter={(val) => `$${val / 1000}k`}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {percentileData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Top Paying Employers */}
      {companyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Building className="h-4 w-4 text-indigo-400" />
              Top Paying Hiring Organizations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {companyData.map((comp, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800/80 flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <span className="text-sm font-semibold text-white block truncate">
                      {comp.name}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      {comp.count} postings
                    </span>
                  </div>
                  <span className="text-sm font-mono font-bold text-emerald-400 shrink-0 ml-2">
                    {formatCurrency(comp.salary)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Narrative block */}
      {narrative && (
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300 leading-relaxed space-y-1">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200">
            <Info className="h-3.5 w-3.5 text-blue-400" />
            <span>Market Intelligence Summary:</span>
          </div>
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
