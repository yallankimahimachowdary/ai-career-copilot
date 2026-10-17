import React from "react"
import {
  CheckCircle,
  AlertOctagon,
  AlertTriangle,
  BookOpen,
  TrendingUp,
  ShieldAlert,
  Sparkles,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ReadinessGauge } from "./ReadinessGauge"
import { formatTitleCase } from "@/lib/utils"

export function SkillGapReport({ report, activeResume }) {
  if (!report) {
    return (
      <div className="p-12 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
        No skill-gap diagnostic report loaded. Select a target job to generate.
      </div>
    )
  }

  const rawCandidateName =
    activeResume?.candidate_name ||
    activeResume?.parsed_data?.contact_info?.name ||
    report.candidate_name ||
    "Candidate"
  const candidateName = formatTitleCase(rawCandidateName)

  const executiveSummary = report.executive_summary
    ? (report.candidate_name && report.candidate_name !== candidateName
        ? report.executive_summary.replaceAll(report.candidate_name, candidateName)
        : report.executive_summary)
    : null

  const strengths = report.confirmed_strengths || []
  const criticalGaps = report.critical_gaps || []
  const growthGaps = report.growth_gaps || []
  const roadmap = report.learning_roadmap || []

  return (
    <div className="space-y-6">
      {/* Top Header Card with Readiness Gauge & Executive Summary */}
      <Card className="border-[#DDD6E7] bg-[#EDE7F6]">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-3 flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-[#7A2D4A] uppercase tracking-wider">
                  Diagnostic Assessment
                </span>
                <Badge variant="primary">Target: {report.job_title}</Badge>
              </div>

              <h3 className="text-xl font-bold text-[#3A3A52]">
                Readiness Diagnostic for {candidateName}
              </h3>

              {executiveSummary && (
                <p className="text-sm text-[#5C5C7A] leading-relaxed pt-1">
                  {executiveSummary}
                </p>
              )}
            </div>

            <div className="shrink-0 w-full md:w-auto flex justify-center">
              <ReadinessGauge score={report.overall_readiness_score || 75} size={110} strokeWidth={9} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirmed Strengths (Verified Qualifications) */}
      <Card className="border-[#DDD6E7] bg-white">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2 text-emerald-800">
              <CheckCircle className="h-4 w-4 text-emerald-700" />
              Confirmed Strengths & Matched Core Capabilities ({strengths.length})
            </CardTitle>
            <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-800 border-emerald-300">
              Verified Candidate Qualification
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {strengths.map((str, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-medium"
              >
                <CheckCircle className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
                <span>{str}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Critical Gaps (Model-Generated Recommendations) */}
      {criticalGaps.length > 0 && (
        <Card className="border-red-200 bg-white">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2 text-red-700">
                <AlertOctagon className="h-4 w-4 text-red-600" />
                Critical Must-Have Gaps ({criticalGaps.length})
              </CardTitle>
              <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700 border-red-200">
                <Sparkles className="h-3 w-3 mr-1" />
                Model-Generated Recommendation
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {criticalGaps.map((gap, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-red-50 border border-red-200 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[#3A3A52] text-sm">{gap.skill}</span>
                    <Badge variant="danger" className="text-[10px]">
                      {gap.importance} priority
                    </Badge>
                  </div>
                  <span className="text-xs text-[#5C5C7A] font-mono">{gap.category}</span>
                </div>
                <p className="text-xs text-red-800 leading-relaxed flex items-start gap-2">
                  <BookOpen className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />
                  <span>{gap.recommendation}</span>
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Growth Gaps */}
      {growthGaps.length > 0 && (
        <Card className="border-amber-200 bg-white">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2 text-amber-800">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Secondary / Nice-to-Have Growth Areas ({growthGaps.length})
              </CardTitle>
              <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-200">
                <Sparkles className="h-3 w-3 mr-1" />
                Suggested Development
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {growthGaps.map((gap, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#3A3A52] text-sm">{gap.skill}</span>
                  <span className="text-xs text-[#5C5C7A] font-mono">{gap.category}</span>
                </div>
                <p className="text-xs text-amber-900 leading-relaxed">{gap.recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Actionable Learning Roadmap */}
      {roadmap.length > 0 && (
        <Card className="border-[#DDD6E7] bg-white">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-[#7A2D4A]">
              <TrendingUp className="h-4 w-4" />
              Actionable 7-to-10 Day Learning Roadmap
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {roadmap.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] text-xs text-[#3A3A52]"
                >
                  <div className="h-5 w-5 rounded-full bg-[#EDE7F6] text-[#7A2D4A] border border-[#DDD6E7] font-bold font-mono text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </div>
                  <span className="leading-relaxed pt-0.5">{item}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Employability & Scientific Disclaimer */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] text-xs text-[#5C5C7A]">
        <ShieldAlert className="h-4 w-4 text-[#7A2D4A] shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong>Employability Notice:</strong> The readiness score and gap recommendations above are generated via algorithmic text and embedding comparison. They represent model-suggested preparation priorities and do not constitute a guarantee of employment, interview selection, or job offer.
        </div>
      </div>
    </div>
  )
}

export default SkillGapReport
