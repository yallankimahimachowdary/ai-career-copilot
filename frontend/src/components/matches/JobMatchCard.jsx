import React from "react"
import {
  Briefcase,
  MapPin,
  Sparkles,
  ChevronRight,
  TrendingUp,
  AlertCircle,
  Building,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { CircularProgress } from "@/components/ui/progress"
import { formatPercent } from "@/lib/utils"

export function JobMatchCard({ match, onSelect }) {
  const fitScore = Math.round((match.final_score || match.composite_score || 0) * 100)
  const skillsBreakdown = match.skills_breakdown || {}
  const matchedSkills = skillsBreakdown.matched_skills || []
  const missingMustHave = skillsBreakdown.missing_must_have || []
  const topShap = match.explanations?.[0]

  const getScoreBadge = (score) => {
    if (score >= 80) return { label: "Strong Fit", variant: "success" }
    if (score >= 65) return { label: "Moderate Fit", variant: "primary" }
    return { label: "Stretch Role", variant: "warning" }
  }

  const badgeInfo = getScoreBadge(fitScore)

  return (
    <Card className="hover:border-blue-500/50 hover:shadow-2xl hover:shadow-blue-950/30 transition-all duration-200 group">
      <CardContent className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* Main Job Info */}
          <div className="space-y-3 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono font-bold text-slate-400">#{match.rank || 1}</span>
              <Badge variant={badgeInfo.variant}>{badgeInfo.label}</Badge>
              {match.remote_allowed && (
                <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
                  Remote
                </Badge>
              )}
              {match.work_type && (
                <span className="text-xs text-slate-500 font-medium">{match.work_type}</span>
              )}
            </div>

            <div>
              <h3 className="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">
                {match.title}
              </h3>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 mt-1">
                <span className="font-semibold text-slate-300 flex items-center gap-1">
                  <Building className="h-3.5 w-3.5 text-slate-500" />
                  {match.company_name}
                </span>
                {match.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-slate-500" />
                    {match.location}
                  </span>
                )}
              </div>
            </div>

            {/* Matched vs Missing Skills Preview */}
            <div className="space-y-1.5 pt-1">
              <div className="flex flex-wrap items-center gap-1 text-xs">
                <span className="text-slate-500 text-[11px] font-medium mr-1">Matched:</span>
                {matchedSkills.slice(0, 4).map((s, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 text-[11px] font-medium border border-emerald-500/20"
                  >
                    {s}
                  </span>
                ))}
                {matchedSkills.length > 4 && (
                  <span className="text-[10px] text-slate-400">+{matchedSkills.length - 4}</span>
                )}
              </div>

              {missingMustHave.length > 0 && (
                <div className="flex flex-wrap items-center gap-1 text-xs">
                  <span className="text-slate-500 text-[11px] font-medium mr-1">Gaps:</span>
                  {missingMustHave.slice(0, 3).map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-300 text-[11px] font-medium border border-rose-500/20"
                    >
                      {s}
                    </span>
                  ))}
                  {missingMustHave.length > 3 && (
                    <span className="text-[10px] text-slate-400">+{missingMustHave.length - 3}</span>
                  )}
                </div>
              )}
            </div>

            {/* Primary SHAP Explanation Driver Quote */}
            {topShap && (
              <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60">
                <Sparkles className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                <span className="truncate">
                  <strong className="text-slate-200">{topShap.display_name}:</strong> {topShap.description}
                </span>
              </div>
            )}
          </div>

          {/* Right Side: Score Gauge & CTA Button */}
          <div className="flex sm:flex-row lg:flex-col items-center justify-between lg:justify-center gap-4 shrink-0 border-t sm:border-t-0 sm:border-l border-slate-800/80 pt-4 sm:pt-0 sm:pl-6">
            <CircularProgress
              value={fitScore}
              size={76}
              strokeWidth={7}
              label={`${fitScore}%`}
              sublabel="Fit Index"
              color={fitScore >= 80 ? "#10b981" : fitScore >= 65 ? "#3b82f6" : "#f59e0b"}
            />

            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelect(match)}
              className="group-hover:border-blue-500 group-hover:bg-blue-600 group-hover:text-white transition-all w-full sm:w-auto"
            >
              <span>Explain Fit & SHAP</span>
              <ChevronRight className="h-3.5 w-3.5 ml-1 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
