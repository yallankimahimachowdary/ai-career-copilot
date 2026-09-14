import * as React from "react"
import { cn } from "@/lib/utils"

export const Button = React.forwardRef(
  ({ className, variant = "primary", size = "default", disabled, children, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"

    const variants = {
      primary:
        "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20 focus:ring-blue-500 active:scale-[0.98]",
      secondary:
        "bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 focus:ring-slate-500 active:scale-[0.98]",
      outline:
        "border border-slate-700 hover:bg-slate-800/60 text-slate-200 focus:ring-slate-400",
      ghost:
        "hover:bg-slate-800/60 text-slate-300 hover:text-white focus:ring-slate-400",
      danger:
        "bg-red-600 hover:bg-red-500 text-white shadow-md shadow-red-500/20 focus:ring-red-500 active:scale-[0.98]",
      gradient:
        "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/25 active:scale-[0.98]",
    }

    const sizes = {
      sm: "text-xs px-2.5 py-1.5 gap-1.5",
      default: "text-sm px-4 py-2 gap-2",
      lg: "text-base px-6 py-3 gap-2.5",
      icon: "h-9 w-9 p-0",
    }

    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(baseStyles, variants[variant] || variants.primary, sizes[size] || sizes.default, className)}
        {...props}
      >
        {children}
      </button>
    )
  }
)
Button.displayName = "Button"
