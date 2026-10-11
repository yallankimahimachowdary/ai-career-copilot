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
      <div className="p-8 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
        No salary compensation data available for this query.
      </div>
    )
  }

  // Distribution percentiles data
  const percentileData = [
    { label: "Min Floor", value: salaryBand.min_annual, color: "#DDD6E7" },
    { label: "25th Pct", value: salaryBand.p25_annual, color: "#EDE7F6" },
    { label: "Median (50th)", value: salaryBand.median_annual, color: "#7A2D4A" },
    { label: "75th Pct", value: salaryBand.p75_annual, color: "#5C5C7A" },
    { label: "Top Ceiling", value: salaryBand.max_annual, color: "#3A3A52" },
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
        <div className="p-3 rounded-xl bg-white border border-[#DDD6E7] shadow-lg text-xs space-y-1">
          <div className="font-bold text-[#3A3A52]">{data.label || data.name}</div>
          <div className="text-[#7A2D4A] font-mono font-semibold">
            {formatCurrency(data.value || data.salary)} / yr
          </div>
          {data.count && (
            <div className="text-[10px] text-[#5C5C7A]">Postings analyzed: {data.count}</div>
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
        <div className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] text-center">
          <span className="text-[11px] text-[#5C5C7A] block font-medium">Minimum Floor</span>
          <span className="text-base font-bold text-[#5C5C7A] font-mono">
            {formatCurrency(salaryBand.min_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] text-center">
          <span className="text-[11px] text-[#5C5C7A] block font-medium">25th Percentile</span>
          <span className="text-base font-bold text-[#3A3A52] font-mono">
            {formatCurrency(salaryBand.p25_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-center shadow-sm">
          <span className="text-[11px] text-[#7A2D4A] block font-semibold">Median Market</span>
          <span className="text-lg font-bold text-[#7A2D4A] font-mono">
            {formatCurrency(salaryBand.median_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] text-center">
          <span className="text-[11px] text-[#5C5C7A] block font-medium">75th Percentile</span>
          <span className="text-base font-bold text-[#3A3A52] font-mono">
            {formatCurrency(salaryBand.p75_annual)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-white border border-[#DDD6E7] text-center">
          <span className="text-[11px] text-[#5C5C7A] block font-medium">Top Ceiling</span>
          <span className="text-base font-bold text-emerald-800 font-mono">
            {formatCurrency(salaryBand.max_annual)}
          </span>
        </div>
      </div>

      {/* Percentiles Bar Chart */}
      <Card className="border-[#DDD6E7] bg-white">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <DollarSign className="h-4 w-4 text-[#7A2D4A]" />
              Annual Compensation Benchmark Spectrum
            </CardTitle>
            <span className="text-xs font-mono text-[#5C5C7A]">
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
                  tick={{ fill: "#5C5C7A", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
                />
                <YAxis
                  tick={{ fill: "#5C5C7A", fontSize: 11 }}
                  tickFormatter={(val) => val >= 100000 ? `₹${(val / 100000).toFixed(0)}L` : `₹${val}`}
                  tickLine={false}
                  axisLine={{ stroke: "#DDD6E7" }}
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
        <Card className="border-[#DDD6E7] bg-white">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <Building className="h-4 w-4 text-[#7A2D4A]" />
              Top Paying Hiring Organizations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {companyData.map((comp, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <span className="text-sm font-semibold text-[#3A3A52] block truncate">
                      {comp.name}
                    </span>
                    <span className="text-xs text-[#5C5C7A] font-mono">
                      {comp.count} postings
                    </span>
                  </div>
                  <span className="text-sm font-mono font-bold text-emerald-800 shrink-0 ml-2">
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
        <div className="p-4 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-xs text-[#3A3A52] leading-relaxed space-y-1">
          <div className="flex items-center gap-1.5 font-semibold text-[#7A2D4A]">
            <Info className="h-3.5 w-3.5 text-[#7A2D4A]" />
            <span>Market Intelligence Summary:</span>
          </div>
          <p>{narrative}</p>
        </div>
      )}
    </div>
  )
}
