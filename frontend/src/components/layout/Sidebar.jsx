import React from "react"
import { NavLink } from "react-router-dom"
import {
  FileText,
  Briefcase,
  GraduationCap,
  TrendingUp,
  Sparkles,
  Bot,
  Layers,
  ChevronRight,
} from "lucide-react"

const NAV_ITEMS = [
  {
    to: "/",
    label: "Resume & Profile",
    icon: FileText,
    badge: "Parser Agent",
    description: "Upload & structured entity extraction",
  },
  {
    to: "/matches",
    label: "Job Matches & XAI",
    icon: Briefcase,
    badge: "Matcher Agent",
    description: "XGBoost + SHAP feature attribution",
  },
  {
    to: "/coach",
    label: "Interview Coach",
    icon: GraduationCap,
    badge: "Coach Agent",
    description: "Skill gaps, QA bank & mock rubric",
  },
  {
    to: "/market",
    label: "Market Insights",
    icon: TrendingUp,
    badge: "Market Agent",
    description: "Salaries, demand & positioning",
  },
]

export function Sidebar({ isConnected = true, isOpen = false, onClose }) {
  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-[#3A3A52]/30 backdrop-blur-xs z-40 lg:hidden transition-opacity"
        />
      )}

      <aside
        className={`fixed lg:static top-0 left-0 z-50 h-screen w-[280px] border-r border-[#DDD6E7] bg-white flex flex-col justify-between shrink-0 shadow-xs transition-transform duration-200 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Brand Header */}
        <div>
          <div className="p-4 sm:p-5 border-b border-[#E5E3EB]">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-[#7A2D4A] p-2 shadow-xs flex items-center justify-center shrink-0">
                <Bot className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#3A3A52] tracking-tight text-base truncate">AI Career Copilot</span>
                </div>
                <p className="text-xs text-[#5C5C7A] truncate">Explainable Multi-Agent System</p>
              </div>
            </div>
          </div>

          {/* Navigation links */}
          <nav className="p-3 space-y-1.5">
            <div className="px-3 py-1.5 text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
              Agent Pipelines
            </div>

            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => onClose && onClose()}
                  className={({ isActive }) =>
                    `group relative flex items-start gap-3 rounded-xl p-3 transition-all duration-150 ${
                      isActive
                        ? "bg-[#FAF7F3] border-l-4 border-l-[#7A2D4A] border-y border-r border-[#DDD6E7] text-[#7A2D4A] shadow-xs font-semibold"
                        : "text-[#3A3A52] hover:text-[#7A2D4A] hover:bg-[#EDE7F6]/60 border border-transparent"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div
                        className={`p-2 rounded-lg mt-0.5 transition-colors shrink-0 ${
                          isActive
                            ? "bg-[#7A2D4A] text-white shadow-xs"
                            : "bg-[#EDE7F6] text-[#3A3A52] group-hover:bg-[#7A2D4A] group-hover:text-white"
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sm leading-snug">{item.label}</span>
                          <ChevronRight
                            className={`h-3.5 w-3.5 transition-transform ${
                              isActive ? "text-[#7A2D4A] translate-x-0.5" : "text-[#797996] group-hover:text-[#7A2D4A]"
                            }`}
                          />
                        </div>
                        <span className="text-xs text-[#5C5C7A] block mt-0.5 leading-tight truncate">
                          {item.description}
                        </span>
                        <span className="inline-block text-[10px] font-mono font-medium text-[#7A2D4A] bg-[#EDE7F6] px-2 py-0.5 rounded-md mt-1.5">
                          {item.badge}
                        </span>
                      </div>
                    </>
                  )}
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* Footer System Status */}
        <div className="p-3 border-t border-[#E5E3EB]">
          <div className="rounded-xl bg-[#FAF7F3] p-2.5 border border-[#DDD6E7] text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span
                  className={`h-2 w-2 rounded-full shrink-0 ${
                    isConnected ? "bg-emerald-600 animate-pulse" : "bg-amber-500"
                  }`}
                />
                <span className="text-[#3A3A52] font-medium text-xs">FastAPI Backend</span>
              </div>
              <span className="text-[10px] font-mono text-[#5C5C7A]">v0.1.0</span>
            </div>
            <div className="text-[10px] text-[#5C5C7A] leading-tight">
              XGBoost + pgvector + TreeSHAP + Ollama (llama3.2:3b)
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
