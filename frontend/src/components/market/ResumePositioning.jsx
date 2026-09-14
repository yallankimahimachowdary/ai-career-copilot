import React from "react"
import {
  Compass,
  CheckCircle,
  XCircle,
  Sparkles,
  TrendingUp,
  MapPin,
  DollarSign,
  Lightbulb,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CircularProgress } from "@/components/ui/progress"
import { formatCurrency } from "@/lib/utils"

export function ResumePositioning({ positioning }) {
  if (!positioning) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No candidate positioning data generated. Make sure a resume is active.
      </div>
    )
  }

  const {
    candidate_name = "Candidate",
    total_relevant_postings = 0,
    skill_alignment = [],
    matched_skill_count = 0,
    coverage_pct = 0,
    salary_expectation_band,
    competitive_locations = [],
    market_narrative,
    positioning_tips = [],
  } = positioning

  const getSignalBadge = (sig) => {
    switch (sig?.toLowerCase()) {
      case "strength":
        return { label: "Core Strength", variant: "success" }
      case "gap":
        return { label: "Market Gap", variant: "danger" }
      case "opportunity":
        return { label: "High Upside", variant: "warning" }
      default:
        return { label: sig, variant: "default" }
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner Card with Coverage Gauge */}
      <Card className="border-blue-500/30 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/20">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-blue-400" />
                <span className="text-xs font-mono font-bold text-blue-400 uppercase tracking-wider">
                  Candidate Market Alignment
                </span>
              </div>
              <h3 className="text-xl font-bold text-white">{candidate_name}'s Market Fit</h3>
              <p className="text-xs text-slate-300 leading-relaxed max-w-xl">
                Benchmark based on {total_relevant_postings.toLocaleString()} relevant postings.
                Identified {matched_skill_count} top-decile market competencies.
              </p>
              {salary_expectation_band?.median_annual && (
                <div className="flex items-center gap-2 text-xs text-emerald-400 pt-1">
                  <DollarSign className="h-4 w-4" />
                  <span>
                    Projected Compensation Range:{" "}
                    <strong>{formatCurrency(salary_expectation_band.median_annual)}</strong> (
                    {formatCurrency(salary_expectation_band.p25_annual)} -{" "}
                    {formatCurrency(salary_expectation_band.p75_annual)})
                  </span>
                </div>
              )}
            </div>

            <div className="shrink-0">
              <CircularProgress
                value={Math.round(coverage_pct)}
                size={90}
                strokeWidth={8}
                label={`${Math.round(coverage_pct)}%`}
                sublabel="Coverage"
                color="#3b82f6"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Skills Alignment Matrix */}
      {skill_alignment.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-400" />
              Skill Demand Alignment Matrix
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-[11px] text-slate-400 uppercase bg-slate-950/60 border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Market Skill Requirement</th>
                    <th className="py-3 px-4">Market Demand</th>
                    <th className="py-3 px-4">Your Resume Status</th>
                    <th className="py-3 px-4">Strategic Signal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {skill_alignment.map((item, idx) => {
                    const badge = getSignalBadge(item.signal)
                    return (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 font-semibold text-white">{item.skill}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">
                          {item.market_demand_pct}%
                        </td>
                        <td className="py-3 px-4">
                          {item.candidate_has ? (
                            <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                              <CheckCircle className="h-3.5 w-3.5" /> Present
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-rose-400 font-medium">
                              <XCircle className="h-3.5 w-3.5" /> Missing
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={badge.variant} className="text-[10px]">
                            {badge.label}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Strategic Positioning Tips & Competitive Locations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {positioning_tips.length > 0 && (
          <Card className="border-amber-500/20 bg-amber-950/10">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2 text-amber-300">
                <Lightbulb className="h-4 w-4 text-amber-400" />
                Strategic Positioning Directives
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2.5 text-xs text-slate-300">
                {positioning_tips.map((tip, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-amber-400 font-bold">•</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {competitive_locations.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2 text-blue-400">
                <MapPin className="h-4 w-4" />
                Most Competitive Geographic Markets
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {competitive_locations.map((loc, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-200"
                  >
                    <MapPin className="h-3 w-3 text-slate-400" />
                    <span>{loc}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {market_narrative && (
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300 leading-relaxed">
          <p>{market_narrative}</p>
        </div>
      )}
    </div>
  )
}
