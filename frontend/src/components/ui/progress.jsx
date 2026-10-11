import * as React from "react"
import { cn } from "@/lib/utils"

export function Progress({ value = 0, max = 100, className, indicatorClassName, showLabel = false }) {
  const percentage = Math.min(Math.max(0, (value / max) * 100), 100)

  return (
    <div className="w-full space-y-1">
      {showLabel && (
        <div className="flex justify-between text-xs text-[#5C5C7A]">
          <span>Progress</span>
          <span>{Math.round(percentage)}%</span>
        </div>
      )}
      <div className={cn("relative h-2 w-full overflow-hidden rounded-full bg-[#EDE7F6]", className)}>
        <div
          className={cn("h-full bg-[#7A2D4A] transition-all duration-500 rounded-full", indicatorClassName)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

export function CircularProgress({ value = 0, size = 64, strokeWidth = 6, label, sublabel, color = "#7A2D4A" }) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (value / 100) * circumference

  return (
    <div className="relative inline-flex flex-col items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-[#EDE7F6]"
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
          fill="transparent"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center text-center">
        <span className="text-sm font-bold text-[#3A3A52]">{label || `${Math.round(value)}%`}</span>
        {sublabel && <span className="text-[10px] text-[#5C5C7A] leading-tight">{sublabel}</span>}
      </div>
    </div>
  )
}
