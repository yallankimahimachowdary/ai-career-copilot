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

export function Sidebar({ isConnected = true }) {
  return (
    <aside className="w-72 border-r border-slate-800/80 bg-slate-950/80 backdrop-blur-xl flex flex-col justify-between shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div>
        <div className="p-6 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 p-0.5 shadow-lg shadow-blue-500/20 flex items-center justify-center">
              <Bot className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white tracking-tight text-base">AI Career Copilot</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  Thesis
                </span>
              </div>
              <p className="text-xs text-slate-400">Explainable Multi-Agent System</p>
            </div>
          </div>
        </div>

        {/* Navigation links */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 py-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Agent Pipelines
          </div>

          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `group relative flex items-start gap-3 rounded-xl p-3 transition-all duration-150 ${
                    isActive
                      ? "bg-slate-900 border border-blue-500/40 text-white shadow-md shadow-blue-950/40"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-900/60 border border-transparent"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div
                      className={`p-2 rounded-lg mt-0.5 transition-colors ${
                        isActive
                          ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                          : "bg-slate-900 text-slate-400 group-hover:text-white"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-sm leading-snug">{item.label}</span>
                        <ChevronRight
                          className={`h-3.5 w-3.5 transition-transform ${
                            isActive ? "text-blue-400 translate-x-0.5" : "text-slate-600 group-hover:text-slate-400"
                          }`}
                        />
                      </div>
                      <span className="text-[11px] text-slate-400 block mt-0.5 leading-tight truncate">
                        {item.description}
                      </span>
                      <span className="inline-block text-[10px] font-mono text-blue-400/90 mt-1">
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
      <div className="p-4 border-t border-slate-800/80">
        <div className="rounded-xl bg-slate-900/80 p-3 border border-slate-800 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                }`}
              />
              <span className="text-slate-300 font-medium">FastAPI Backend</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">v0.1.0</span>
          </div>
          <div className="text-[11px] text-slate-400 leading-tight">
            XGBoost + pgvector + TreeSHAP + Gemini/LLM
          </div>
        </div>
      </div>
    </aside>
  )
}
