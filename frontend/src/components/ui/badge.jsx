import * as React from "react"
import { cn } from "@/lib/utils"

export function Badge({ className, variant = "default", children, ...props }) {
  const variants = {
    default: "bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750",
    primary: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    danger: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    purple: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    outline: "border border-slate-700 text-slate-300",
  }

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors tracking-wide",
        variants[variant] || variants.default,
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
