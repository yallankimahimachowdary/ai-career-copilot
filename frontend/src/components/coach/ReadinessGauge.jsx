import React from "react"
import { CircularProgress } from "@/components/ui/progress"

export function ReadinessGauge({ score = 0, size = 100, strokeWidth = 8 }) {
  const roundScore = Math.round(score)

  const getColor = (s) => {
    if (s >= 80) return "#7A2D4A" // Burgundy top score
    if (s >= 65) return "#5C5C7A" // Slate solid
    if (s >= 50) return "#D97706" // Amber
    return "#DC2626" // Red
  }

  const getLabel = (s) => {
    if (s >= 85) return "Interview Ready"
    if (s >= 70) return "Solid Candidate"
    if (s >= 50) return "Moderate Gaps"
    return "High Prep Needed"
  }

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-white border border-[#DDD6E7] shadow-sm">
      <CircularProgress
        value={roundScore}
        size={size}
        strokeWidth={strokeWidth}
        label={`${roundScore}%`}
        sublabel="Readiness"
        color={getColor(roundScore)}
      />
      <div className="mt-2 text-center">
        <span className="text-xs font-bold text-[#3A3A52] block">{getLabel(roundScore)}</span>
        <span className="text-[10px] text-[#5C5C7A]">Diagnostic Readiness Index</span>
      </div>
    </div>
  )
}
