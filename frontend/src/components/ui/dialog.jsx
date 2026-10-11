import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export function Dialog({ open, onOpenChange, children }) {
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && open) {
        onOpenChange?.(false)
      }
    }
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = "unset"
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => {
      document.body.style.overflow = "unset"
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-10">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={() => onOpenChange?.(false)}
      />
      {/* Content Container */}
      <div className="relative z-50 w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-[#DDD6E7] bg-white p-6 shadow-xl transition-all animate-in zoom-in-95 duration-200 text-[#3A3A52]">
        <button
          onClick={() => onOpenChange?.(false)}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-[#5C5C7A] hover:bg-[#EDE7F6] hover:text-[#3A3A52] transition-colors cursor-pointer"
        >
          <X className="h-5 w-5" />
        </button>
        {children}
      </div>
    </div>
  )
}

export function DialogHeader({ className, children }) {
  return <div className={cn("flex flex-col space-y-1.5 pb-4 border-b border-[#E5E3EB]", className)}>{children}</div>
}

export function DialogTitle({ className, children }) {
  return <h2 className={cn("text-xl font-bold tracking-tight text-[#3A3A52]", className)}>{children}</h2>
}

export function DialogDescription({ className, children }) {
  return <p className={cn("text-sm text-[#5C5C7A]", className)}>{children}</p>
}
