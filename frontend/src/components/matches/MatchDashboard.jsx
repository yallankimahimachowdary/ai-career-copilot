import React, { useState } from "react"
import {
  Search,
  Filter,
  Sparkles,
  SlidersHorizontal,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { JobMatchCard } from "./JobMatchCard"
import { MatchDetailModal } from "./MatchDetailModal"

export function MatchDashboard({
  matches = [],
  isLoading,
  error,
  activeResume,
  onRunMatch,
  onStartCoaching,
}) {
  const [selectedMatch, setSelectedMatch] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [locationFilter, setLocationFilter] = useState("")
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [minScore, setMinScore] = useState(0)

  // Filter client-side if matches already returned
  const filteredMatches = matches.filter((m) => {
    const finalScore = (m.final_score || m.composite_score || 0) * 100
    if (finalScore < minScore) return false
    if (remoteOnly && !m.remote_allowed) return false
    if (locationFilter.trim()) {
      const q = locationFilter.toLowerCase()
      const loc = (m.location || "").toLowerCase()
      const comp = (m.company_name || "").toLowerCase()
      const tit = (m.title || "").toLowerCase()
      if (!loc.includes(q) && !comp.includes(q) && !tit.includes(q)) return false
    }
    return true
  })

  const handleCardClick = (match) => {
    setSelectedMatch(match)
    setModalOpen(true)
  }

  const handleRunSearch = () => {
    if (onRunMatch) {
      onRunMatch({
        location: locationFilter || undefined,
        remote_only: remoteOnly,
        min_score: minScore / 100,
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Controls & Filter Bar */}
      <Card className="border-[#DDD6E7] bg-white shadow-xs">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Location or Keyword Filter */}
              <div className="relative">
                <Search className="h-4 w-4 absolute left-3 top-3 text-[#797996]" />
                <Input
                  placeholder="Filter location, company, role..."
                  value={locationFilter}
                  onChange={(e) => setLocationFilter(e.target.value)}
                  className="pl-9"
                />
              </div>

              {/* Min Score Slider */}
              <div className="flex flex-col justify-center px-2 space-y-1">
                <div className="flex justify-between text-xs text-[#5C5C7A]">
                  <span>Min Score:</span>
                  <span className="font-mono text-[#7A2D4A] font-semibold">{minScore}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="90"
                  step="5"
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  className="w-full accent-[#7A2D4A] cursor-pointer h-1.5 bg-[#EDE7F6] rounded-lg"
                />
              </div>

              {/* Remote Only Toggle */}
              <div className="flex items-center gap-2 px-2">
                <label className="flex items-center gap-2 text-xs text-[#3A3A52] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={remoteOnly}
                    onChange={(e) => setRemoteOnly(e.target.checked)}
                    className="rounded border-[#DDD6E7] bg-white text-[#7A2D4A] focus:ring-[#7A2D4A] h-4 w-4"
                  />
                  <span>Remote roles only</span>
                </label>
              </div>
            </div>

            {/* Run Match Action Button */}
            <Button
              variant="primary"
              onClick={handleRunSearch}
              disabled={isLoading || !activeResume}
              className="shrink-0"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Computing SHAP & Fits...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  <span>Find My Top Matches</span>
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
          <div>
            <span className="font-semibold">Matching Service Error: </span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Active Resume Context Notice */}
      {!activeResume && (
        <div className="p-8 text-center rounded-2xl border border-dashed border-[#DDD6E7] bg-white space-y-2">
          <p className="text-sm font-medium text-[#3A3A52]">No active candidate profile loaded</p>
          <p className="text-xs text-[#5C5C7A]">
            Please upload a resume in the "Resume & Profile" tab or click "Load Demo Profile" in the top bar.
          </p>
        </div>
      )}

      {/* Matches List */}
      {isLoading ? (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-[#DDD6E7] bg-[#EDE7F6]/60 flex items-center gap-3">
            <Loader2 className="h-5 w-5 text-[#7A2D4A] animate-spin shrink-0" />
            <div>
              <p className="text-xs font-semibold text-[#3A3A52]">Running Hybrid Matcher & TreeSHAP Engine</p>
              <p className="text-[11px] text-[#5C5C7A]">
                Querying vector embeddings, re-ranking with XGBoost, and computing Shapley feature attribution...
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-32 rounded-xl border border-[#DDD6E7] bg-white p-5 animate-pulse flex flex-col justify-between"
              >
                <div className="flex justify-between items-start">
                  <div className="space-y-2 w-2/3">
                    <div className="h-4 bg-[#EDE7F6] rounded w-3/4" />
                    <div className="h-3 bg-[#FAF7F3] rounded w-1/2" />
                  </div>
                  <div className="h-10 w-10 rounded-full bg-[#EDE7F6]" />
                </div>
                <div className="flex gap-2">
                  <div className="h-5 bg-[#EDE7F6] rounded w-16" />
                  <div className="h-5 bg-[#EDE7F6] rounded w-20" />
                  <div className="h-5 bg-[#EDE7F6] rounded w-14" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : filteredMatches.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-[#5C5C7A] px-1">
            <span>
              Displaying <strong className="text-[#3A3A52]">{filteredMatches.length}</strong> ranked opportunities
            </span>
            <span>Two-stage retrieval (semantic + XGBoost Re-rank)</span>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {filteredMatches.map((match) => (
              <JobMatchCard key={match.job_id} match={match} onSelect={handleCardClick} />
            ))}
          </div>
        </div>
      ) : activeResume ? (
        <div className="p-12 text-center rounded-2xl border border-[#DDD6E7] bg-white space-y-3">
          <Sparkles className="h-8 w-8 text-[#7A2D4A] mx-auto" />
          <p className="text-sm font-semibold text-[#3A3A52]">No matches found matching these filters.</p>
          <p className="text-xs text-[#5C5C7A]">
            Try lowering your minimum score threshold or clearing location filters.
          </p>
        </div>
      ) : null}

      {/* Modal for Deep Dive & SHAP */}
      <MatchDetailModal
        match={selectedMatch}
        resumeId={activeResume?.id}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onStartCoaching={onStartCoaching}
      />
    </div>
  )
}
