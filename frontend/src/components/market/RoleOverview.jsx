import React from "react"
import {
  Briefcase,
  Globe,
  Building,
  DollarSign,
  PieChart,
  Users,
  CheckCircle,
  Info,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatCurrency } from "@/lib/utils"

export function RoleOverview({ overview }) {
  if (!overview) {
    return (
      <Card className="border-[#DDD6E7] bg-white text-center p-8">
        <CardContent className="space-y-3">
          <Briefcase className="h-8 w-8 text-[#5C5C7A] mx-auto" />
          <h3 className="text-base font-semibold text-[#3A3A52]">Market Intelligence Ready</h3>
          <p className="text-xs text-[#5C5C7A] max-w-md mx-auto">
            Click &quot;Analyze Market Dynamics&quot; above to query compensation percentiles, in-demand skills, and geographic hiring distribution across live Indian job postings.
          </p>
        </CardContent>
      </Card>
    )
  }

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
      {total_postings === 0 && (
        <Card className="border-amber-200 bg-amber-50 text-amber-900">
          <CardContent className="p-4 flex items-start gap-3">
            <Info className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <p className="font-semibold text-amber-900">
                No active postings found directly matching "{title_query}"
              </p>
              <p className="text-[#5C5C7A]">
                The current labor market dataset does not have indexed postings matching this specific role query. Try searching for related titles, broader domain keywords (such as "Biotechnology", "Scientist", or "Software Engineer"), or clearing the location filter.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-[#DDD6E7] bg-white shadow-xs">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
              Total Active Postings
            </span>
            <div className="text-2xl font-bold text-[#3A3A52] font-mono">
              {total_postings.toLocaleString()}
            </div>
            <p className="text-[11px] text-[#5C5C7A]">Indexed in PostgreSQL pgvector</p>
          </CardContent>
        </Card>

        <Card className="border-[#DDD6E7] bg-white shadow-xs">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
              Remote Availability
            </span>
            <div className="text-2xl font-bold text-[#3A3A52] font-mono">{remote_pct}%</div>
            <p className="text-[11px] text-[#5C5C7A]">Permits WFH / Geographic Flexibility</p>
          </CardContent>
        </Card>

        <Card className="border-[#DDD6E7] bg-white shadow-xs">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
              Median Salary
            </span>
            <div className="text-2xl font-bold text-[#7A2D4A] font-mono">
              {formatCurrency(salary_band?.median_annual)}
            </div>
            <p className="text-[11px] text-[#5C5C7A]">Annual Total Compensation Floor</p>
          </CardContent>
        </Card>

        <Card className="border-[#DDD6E7] bg-white shadow-xs">
          <CardContent className="p-5 space-y-1">
            <span className="text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
              Full-Time Ratio
            </span>
            <div className="text-2xl font-bold text-[#3A3A52] font-mono">
              {total_postings > 0 ? Math.round((fullTime / total_postings) * 100) : 85}%
            </div>
            <p className="text-[11px] text-[#5C5C7A]">Direct Permanent Employment</p>
          </CardContent>
        </Card>
      </div>

      {/* Work Type Breakdown & Leading Employers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Work Type */}
        <Card className="border-[#DDD6E7] bg-white">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <PieChart className="h-4 w-4 text-[#7A2D4A]" />
              Contract & Engagement Mix
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-[#5C5C7A]">Full-Time</span>
                <span className="font-mono text-[#3A3A52] font-semibold">{fullTime}</span>
              </div>
              <div className="h-2 w-full bg-[#EDE7F6] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#7A2D4A] rounded-full"
                  style={{ width: `${(fullTime / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-[#5C5C7A]">Contract / Freelance</span>
                <span className="font-mono text-[#3A3A52] font-semibold">{contract}</span>
              </div>
              <div className="h-2 w-full bg-[#EDE7F6] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#5C5C7A] rounded-full"
                  style={{ width: `${(contract / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-[#5C5C7A]">Internship / Co-op</span>
                <span className="font-mono text-[#3A3A52] font-semibold">{internship}</span>
              </div>
              <div className="h-2 w-full bg-[#EDE7F6] rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-600 rounded-full"
                  style={{ width: `${(internship / (total_postings || 1)) * 100}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Leading Employers */}
        <Card className="border-[#DDD6E7] bg-white">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-[#3A3A52]">
              <Building className="h-4 w-4 text-[#7A2D4A]" />
              Leading Hiring Employers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {top_companies.map((company, idx) => {
                const name = typeof company === "object" && company !== null
                  ? (company.company_name || company.name || "Company")
                  : String(company)
                return (
                  <div
                    key={idx}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#FAF7F3] border border-[#DDD6E7] text-xs text-[#3A3A52]"
                  >
                    <Building className="h-3 w-3 text-[#5C5C7A]" />
                    <span>{name}</span>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Narrative & Data Quality Footnote */}
      {narrative && (
        <Card className="border-[#DDD6E7] bg-[#EDE7F6]">
          <CardContent className="p-5 space-y-2 text-xs text-[#3A3A52] leading-relaxed">
            <h4 className="font-semibold text-[#7A2D4A]">Labor Market Synthesis:</h4>
            <p>{narrative}</p>
            {data_quality_note && (
              <p className="text-[11px] text-[#5C5C7A] pt-1 font-mono">{data_quality_note}</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
