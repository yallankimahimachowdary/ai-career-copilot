import React from "react"
import {
  CheckCircle,
  AlertOctagon,
  AlertTriangle,
  BookOpen,
  Calendar,
  Sparkles,
  ArrowRight,
  TrendingUp,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ReadinessGauge } from "./ReadinessGauge"

export function SkillGapReport({ report, onProceedToQuestions }) {
  if (!report) {
    return (
      <div className="p-12 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No skill-gap diagnostic report loaded. Select a target job to generate.
      </div>
    )
  }

  const strengths = report.confirmed_strengths || []
  const criticalGaps = report.critical_gaps || []
  const growthGaps = report.growth_gaps || []
  const roadmap = report.learning_roadmap || []

  return (
    <div className="space-y-6">
      {/* Top Header Card with Readiness Gauge & Executive Summary */}
      <Card className="border-blue-500/20 bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/20">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-3 flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-blue-400 uppercase tracking-wider">
                  Step 1: Diagnostic Assessment
                </span>
                <Badge variant="primary">Target: {report.job_title}</Badge>
              </div>

              <h3 className="text-xl font-bold text-white">
                Readiness Diagnostic for {report.candidate_name || "Candidate"}
              </h3>

              {report.executive_summary && (
                <p className="text-sm text-slate-300 leading-relaxed pt-1">
                  {report.executive_summary}
                </p>
              )}
            </div>

            <div className="shrink-0 w-full md:w-auto flex justify-center">
              <ReadinessGauge score={report.overall_readiness_score || 75} size={110} strokeWidth={9} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirmed Strengths */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2 text-emerald-400">
            <CheckCircle className="h-4 w-4" />
            Confirmed Strengths & Matched Core Capabilities ({strengths.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {strengths.map((str, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/30 border border-emerald-500/20 text-xs text-emerald-300 font-medium"
              >
                <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                <span>{str}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Critical Gaps */}
      {criticalGaps.length > 0 && (
        <Card className="border-rose-500/30">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-rose-400">
              <AlertOctagon className="h-4 w-4" />
              Critical Must-Have Gaps ({criticalGaps.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {criticalGaps.map((gap, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/20 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">{gap.skill}</span>
                    <Badge variant="danger" className="text-[10px]">
                      {gap.importance} priority
                    </Badge>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">{gap.category}</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed flex items-start gap-2">
                  <BookOpen className="h-3.5 w-3.5 text-rose-400 shrink-0 mt-0.5" />
                  <span>{gap.recommendation}</span>
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Growth Gaps */}
      {growthGaps.length > 0 && (
        <Card className="border-amber-500/30">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-amber-400">
              <AlertTriangle className="h-4 w-4" />
              Secondary / Nice-to-Have Growth Areas ({growthGaps.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {growthGaps.map((gap, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/20 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white text-sm">{gap.skill}</span>
                  <span className="text-xs text-slate-400 font-mono">{gap.category}</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{gap.recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Actionable Learning Roadmap */}
      {roadmap.length > 0 && (
        <Card className="border-indigo-500/30">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-indigo-400">
              <TrendingUp className="h-4 w-4" />
              Actionable 7-to-10 Day Learning Roadmap
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {roadmap.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs text-slate-300"
                >
                  <div className="h-5 w-5 rounded-full bg-indigo-600/30 text-indigo-400 border border-indigo-500/40 font-bold font-mono text-[11px] flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </div>
                  <span className="leading-relaxed pt-0.5">{item}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
