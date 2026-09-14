import React from "react"
import { Progress } from "@/components/ui/progress"
import { formatPercent } from "@/lib/utils"

export function ScoreBreakdown({ features = {} }) {
  const mustHave = features.must_have_skill_match || 0
  const expMatch = features.experience_penalty
    ? Math.max(0, 1 - features.experience_penalty * 3)
    : Math.min(1, (features.candidate_years_experience || 0) / Math.max(1, features.job_required_years || 1))
  const eduMatch = features.education_level_match != null ? features.education_level_match : 1.0

  const items = [
    {
      label: "Skills Alignment",
      value: mustHave,
      color: "bg-blue-500",
      text: formatPercent(mustHave),
    },
    {
      label: "Experience Fit",
      value: Math.min(1, Math.max(0, expMatch)),
      color: expMatch >= 0.75 ? "bg-emerald-500" : expMatch >= 0.4 ? "bg-amber-500" : "bg-rose-500",
      text: formatPercent(expMatch),
    },
    {
      label: "Education Match",
      value: eduMatch,
      color: "bg-purple-500",
      text: formatPercent(eduMatch),
    },
  ]

  return (
    <div className="space-y-2.5">
      {items.map((item, idx) => (
        <div key={idx} className="space-y-1">
          <div className="flex justify-between text-xs font-medium">
            <span className="text-slate-400">{item.label}</span>
            <span className="text-slate-200 font-mono">{item.text}</span>
          </div>
          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full ${item.color} rounded-full transition-all duration-500`}
              style={{ width: `${Math.round(item.value * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
