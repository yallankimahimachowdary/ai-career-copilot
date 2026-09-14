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
      window.addEventListener("keydown", handleKeyDown)
    } else {
      document.body.style.overflow = "unset"
    }
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
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        onClick={() => onOpenChange?.(false)}
      />
      {/* Content Container */}
      <div className="relative z-50 w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl transition-all animate-in zoom-in-95 duration-200 text-slate-100">
        <button
          onClick={() => onOpenChange?.(false)}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
        >
          <X className="h-5 w-5" />
        </button>
        {children}
      </div>
    </div>
  )
}

export function DialogHeader({ className, children }) {
  return <div className={cn("flex flex-col space-y-1.5 pb-4 border-b border-slate-800", className)}>{children}</div>
}

export function DialogTitle({ className, children }) {
  return <h2 className={cn("text-xl font-bold tracking-tight text-white", className)}>{children}</h2>
}

export function DialogDescription({ className, children }) {
  return <p className={cn("text-sm text-slate-400", className)}>{children}</p>
}
