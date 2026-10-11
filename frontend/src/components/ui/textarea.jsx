import * as React from "react"
import { cn } from "@/lib/utils"

export const Textarea = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-lg border border-[#DDD6E7] bg-white px-3 py-2 text-sm text-[#3A3A52] placeholder:text-[#797996] focus:outline-none focus:ring-2 focus:ring-[#7A2D4A] focus:border-[#7A2D4A] disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-150 resize-y shadow-xs",
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = "Textarea"
