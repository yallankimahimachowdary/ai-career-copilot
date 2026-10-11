import * as React from "react"
import { cn } from "@/lib/utils"

export const Button = React.forwardRef(
  ({ className, variant = "primary", size = "default", disabled, children, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#7A2D4A] focus:ring-offset-[#FAF7F3] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"

    const variants = {
      primary:
        "bg-[#7A2D4A] hover:bg-[#63233B] active:bg-[#4F1C2F] text-white shadow-sm focus:ring-[#7A2D4A] active:scale-[0.98]",
      secondary:
        "bg-[#EDE7F6] hover:bg-[#DDD6E7] text-[#3A3A52] border border-[#DDD6E7] focus:ring-[#7A2D4A] active:scale-[0.98]",
      outline:
        "border border-[#DDD6E7] bg-white hover:bg-[#EDE7F6]/50 text-[#3A3A52] focus:ring-[#7A2D4A]",
      ghost:
        "hover:bg-[#EDE7F6] text-[#5C5C7A] hover:text-[#3A3A52] focus:ring-[#7A2D4A]",
      danger:
        "bg-red-600 hover:bg-red-700 text-white shadow-sm focus:ring-red-500 active:scale-[0.98]",
      gradient:
        "bg-[#7A2D4A] hover:bg-[#63233B] text-white shadow-sm hover:shadow active:scale-[0.98]",
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
