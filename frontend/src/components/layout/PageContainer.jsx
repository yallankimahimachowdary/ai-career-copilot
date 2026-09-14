import React from "react"

export function PageContainer({ title, subtitle, badge, action, children }) {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in-50 duration-300">
      {/* Header section */}
      {(title || subtitle || action) && (
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/60">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">{title}</h1>
              {badge && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {badge}
                </span>
              )}
            </div>
            {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
          </div>
          {action && <div className="flex items-center gap-3">{action}</div>}
        </div>
      )}

      {/* Main content */}
      <div>{children}</div>
    </div>
  )
}
