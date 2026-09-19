import React from "react"
import { ExternalLink, Sparkles, User, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

export function Header({ activeResume, onSelectDemoResume, isConnected, onRefresh }) {
  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-ping" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            System Live
          </span>
        </div>

        {activeResume ? (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-blue-500/30 text-xs">
            <User className="h-3.5 w-3.5 text-blue-400" />
            <span className="text-slate-300">Active Profile:</span>
            <span className="text-white font-semibold">{activeResume.candidate_name || activeResume.filename}</span>
            <span className="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded font-mono">
              {activeResume.skills_count || activeResume.parsed_data?.skills?.length || 0} skills
            </span>
          </div>
        ) : (
          <div className="text-xs text-slate-400 italic">No resume selected (upload one or use demo)</div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={onSelectDemoResume}
          className="text-xs border-indigo-500/40 text-indigo-300 hover:bg-indigo-950/30 hover:text-indigo-200"
        >
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          Load Demo Profile
        </Button>

        {onRefresh && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onRefresh}
            title="Refresh active view"
            className="h-8 w-8 text-slate-400 hover:text-white"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        )}

        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors px-2 py-1 rounded-md hover:bg-slate-900"
        >
          <span>Swagger API Docs</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </header>
  )
}
