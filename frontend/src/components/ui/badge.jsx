import * as React from "react"
import { cn } from "@/lib/utils"

export function Badge({ className, variant = "default", children, ...props }) {
  const variants = {
    default: "bg-[#EDE7F6] text-[#3A3A52] border-[#DDD6E7]",
    primary: "bg-[#F9EBF0] text-[#7A2D4A] border-[#DDD6E7]",
    burgundy: "bg-[#7A2D4A] text-white border-[#7A2D4A]",
    lavender: "bg-[#EDE7F6] text-[#3A3A52] border-[#DDD6E7]",
    success: "bg-emerald-50 text-emerald-800 border-emerald-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    danger: "bg-red-50 text-red-800 border-red-200",
    purple: "bg-[#EDE7F6] text-[#7A2D4A] border-[#DDD6E7]",
    outline: "border border-[#DDD6E7] text-[#3A3A52] bg-white",
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
