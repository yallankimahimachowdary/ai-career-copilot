import React from "react"

export function PageContainer({ title, subtitle, badge, action, children }) {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in-50 duration-300">
      {/* Header section */}
      {(title || subtitle || action) && (
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#DDD6E7]">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#3A3A52]">{title}</h1>
              {badge && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#EDE7F6] text-[#7A2D4A] border border-[#DDD6E7]">
                  {badge}
                </span>
              )}
            </div>
            {subtitle && <p className="text-sm text-[#5C5C7A]">{subtitle}</p>}
          </div>
          {action && <div className="flex items-center gap-3">{action}</div>}
        </div>
      )}

      {/* Main content */}
      <div>{children}</div>
    </div>
  )
}
