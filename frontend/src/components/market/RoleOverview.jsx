import React from "react"
import {
  Briefcase,
  Globe,
  Building,
  DollarSign,
  PieChart,
  Users,
  CheckCircle,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatCurrency } from "@/lib/utils"

export function RoleOverview({ overview }) {
  if (!overview) return null

  const {
    title_query = "Software Engineer",
    total_postings = 0,
    remote_pct = 0,
    work_type_breakdown = {},
    top_companies = [],
    salary_band,
    narrative,
    data_quality_note,
  } = overview

  const fullTime = work_type_breakdown.full_time || 0
  const contract = work_type_breakdown.contract || 0
  const partTime = work_type_breakdown.part_time || 0
  const internship = work_type_breakdown.internship || 0

  return (
    <div className="space-y-6">
      {/* 4 Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-blue-500/20 bg-gradient-to-br from-slate-900 to-blue-950/20">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Total Active Postings
            </span>
            <div className="text-2xl font-bold text-white font-mono">
              {total_postings.toLocaleString()}
            </div>
            <p className="text-[11px] text-blue-400">Indexed in PostgreSQL pgvector</p>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-gradient-to-br from-slate-900 to-emerald-950/20">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Remote Availability
            </span>
            <div className="text-2xl font-bold text-emerald-400 font-mono">{remote_pct}%</div>
            <p className="text-[11px] text-emerald-400/80">Permits WFH / Geographic Flexibility</p>
          </CardContent>
        </Card>

        <Card className="border-purple-500/20 bg-gradient-to-br from-slate-900 to-purple-950/20">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Median Salary
            </span>
            <div className="text-2xl font-bold text-purple-400 font-mono">
              {formatCurrency(salary_band?.median_annual)}
            </div>
            <p className="text-[11px] text-purple-400/80">Annual Total Compensation Floor</p>
          </CardContent>
        </Card>

        <Card className="border-amber-500/20 bg-gradient-to-br from-slate-900 to-amber-950/20">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Full-Time Ratio
            </span>
            <div className="text-2xl font-bold text-amber-400 font-mono">
              {total_postings > 0 ? Math.round((fullTime / total_postings) * 100) : 85}%
            </div>
            <p className="text-[11px] text-amber-400/80">Direct Permanent Employment</p>
          </CardContent>
        </Card>
      </div>

      {/* Work Type Breakdown & Leading Employers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Work Type */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <PieChart className="h-4 w-4 text-blue-400" />
              Contract & Engagement Mix
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300">Full-Time</span>
                <span className="font-mono text-white font-semibold">{fullTime}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${(fullTime / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300">Contract / Freelance</span>
                <span className="font-mono text-white font-semibold">{contract}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full"
                  style={{ width: `${(contract / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300">Internship / Co-op</span>
                <span className="font-mono text-white font-semibold">{internship}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full"
                  style={{ width: `${(internship / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Leading Employers */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Building className="h-4 w-4 text-indigo-400" />
              Leading Hiring Employers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {top_companies.map((company, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-200"
                >
                  <Building className="h-3 w-3 text-slate-400" />
                  <span>{company}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Narrative & Data Quality Footnote */}
      {narrative && (
        <Card className="border-blue-500/20 bg-slate-900/60">
          <CardContent className="p-5 space-y-2 text-xs text-slate-300 leading-relaxed">
            <h4 className="font-semibold text-white">Labor Market Synthesis:</h4>
            <p>{narrative}</p>
            {data_quality_note && (
              <p className="text-[11px] text-slate-400 pt-1 font-mono">{data_quality_note}</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
