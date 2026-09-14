import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { PageContainer } from "@/components/layout/PageContainer"
import { MatchDashboard } from "@/components/matches/MatchDashboard"
import { matchApi } from "@/api/matchApi"
import { mockMatches } from "@/data/mockData"

export function MatchesPage({ activeResume, onSelectJobForCoach }) {
  const [matches, setMatches] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const fetchMatches = async (params = {}) => {
    if (!activeResume?.id) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await matchApi.matchJobsForResume(activeResume.id, params)
      if (data && data.matches && data.matches.length > 0) {
        setMatches(data.matches)
      } else {
        // Fallback to mock matches if database returned zero
        setMatches(mockMatches.matches)
      }
    } catch (err) {
      console.warn("Match API call failed, using mock matches fallback:", err.message)
      setMatches(mockMatches.matches)
      setError("Connected to offline demonstration mode: " + err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (activeResume?.id) {
      fetchMatches()
    } else {
      setMatches(mockMatches.matches)
    }
  }, [activeResume?.id])

  const handleStartCoaching = (match) => {
    if (onSelectJobForCoach) {
      onSelectJobForCoach(match)
    }
    navigate(`/coach?job_id=${match.job_id}`)
  }

  return (
    <PageContainer
      title="Job Matching & Explainable AI (XAI)"
      subtitle="Hybrid pgvector retrieval with XGBoost re-ranking and local TreeSHAP attribution"
      badge="Matcher Agent"
    >
      <MatchDashboard
        matches={matches}
        isLoading={isLoading}
        error={error}
        activeResume={activeResume}
        onRunMatch={fetchMatches}
        onStartCoaching={handleStartCoaching}
      />
    </PageContainer>
  )
}
