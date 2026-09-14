import React from "react"
import { CircularProgress } from "@/components/ui/progress"

export function ReadinessGauge({ score = 0, size = 100, strokeWidth = 8 }) {
  const roundScore = Math.round(score)

  const getColor = (s) => {
    if (s >= 80) return "#10b981" // Emerald
    if (s >= 65) return "#3b82f6" // Blue
    if (s >= 50) return "#f59e0b" // Amber
    return "#f43f5e" // Rose
  }

  const getLabel = (s) => {
    if (s >= 85) return "Interview Ready"
    if (s >= 70) return "Solid Candidate"
    if (s >= 50) return "Moderate Gaps"
    return "High Prep Needed"
  }

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-slate-900/80 border border-slate-800">
      <CircularProgress
        value={roundScore}
        size={size}
        strokeWidth={strokeWidth}
        label={`${roundScore}%`}
        sublabel="Readiness"
        color={getColor(roundScore)}
      />
      <div className="mt-2 text-center">
        <span className="text-xs font-bold text-white block">{getLabel(roundScore)}</span>
        <span className="text-[10px] text-slate-400">Diagnostic Readiness Index</span>
      </div>
    </div>
  )
}
