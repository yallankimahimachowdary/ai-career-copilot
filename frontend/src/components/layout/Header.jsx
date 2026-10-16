import React from "react"
import { ExternalLink, Sparkles, User, RefreshCw, Menu } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatTitleCase } from "@/lib/utils"

export function Header({ activeResume, onSelectDemoResume, isConnected, onRefresh, onToggleSidebar }) {
  const displayName = activeResume?.candidate_name
    ? formatTitleCase(activeResume.candidate_name)
    : activeResume?.filename || "Candidate"

  return (
    <header className="h-16 border-b border-[#DDD6E7] bg-white px-4 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-2 rounded-lg text-[#5C5C7A] hover:bg-[#EDE7F6] hover:text-[#3A3A52] transition-colors"
            aria-label="Open Navigation Menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}

        <div className="hidden sm:flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-emerald-600 animate-ping" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[#5C5C7A]">
            System Live
          </span>
        </div>

        {activeResume ? (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#EDE7F6] border border-[#DDD6E7] text-xs">
            <User className="h-3.5 w-3.5 text-[#7A2D4A] shrink-0" />
            <span className="text-[#5C5C7A] hidden md:inline">Active Profile:</span>
            <span className="text-[#3A3A52] font-semibold truncate max-w-[150px] sm:max-w-none">{displayName}</span>
            {activeResume.isDemo && (
              <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider">
                Demo Profile
              </span>
            )}
            <span className="text-[10px] text-[#7A2D4A] bg-white border border-[#DDD6E7] px-1.5 py-0.5 rounded font-mono font-medium">
              {activeResume.skills_count || activeResume.parsed_data?.skills?.length || 0} skills
            </span>
          </div>
        ) : (
          <div className="text-xs text-[#5C5C7A] italic">No resume selected (upload one or use demo)</div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={onSelectDemoResume}
          className="text-xs border-[#DDD6E7] text-[#7A2D4A] hover:bg-[#DDD6E7]"
        >
          <Sparkles className="h-3.5 w-3.5 text-[#7A2D4A]" />
          Load Demo Profile
        </Button>

        {onRefresh && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onRefresh}
            title="Refresh active view"
            className="h-8 w-8 text-[#5C5C7A] hover:text-[#3A3A52] hover:bg-[#EDE7F6]"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        )}

        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-[#5C5C7A] hover:text-[#3A3A52] transition-colors px-2 py-1 rounded-md hover:bg-[#EDE7F6]"
        >
          <span>Swagger API Docs</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </header>
  )
}
