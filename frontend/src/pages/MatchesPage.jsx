import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { PageContainer } from "@/components/layout/PageContainer"
import { MatchDashboard } from "@/components/matches/MatchDashboard"
import { matchApi } from "@/api/matchApi"
import { demoMatches } from "@/demo/demoData"

export function MatchesPage({ activeResume, onSelectJobForCoach }) {
  const [matches, setMatches] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [isDemoMatches, setIsDemoMatches] = useState(false)
  const navigate = useNavigate()

  const fetchMatches = async (params = {}) => {
    if (!activeResume?.id) {
      setMatches([])
      setIsDemoMatches(false)
      return
    }
    setIsLoading(true)
    setError(null)
    setIsDemoMatches(false)
    try {
      const data = await matchApi.matchJobsForResume(activeResume.id, params)
      if (data && data.matches && data.matches.length > 0) {
        setMatches(data.matches)
      } else if (activeResume?.isDemo) {
        // Explicit demo profile uses illustrative demo matches
        setMatches(demoMatches)
        setIsDemoMatches(true)
      } else {
        // Real profile returned 0 matches from database
        setMatches([])
      }
    } catch (err) {
      console.warn("Match API call failed:", err.message)
      if (activeResume?.isDemo) {
        setMatches(demoMatches)
        setIsDemoMatches(true)
      } else {
        setMatches([])
        setError("Matching service unavailable: " + err.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (activeResume?.id) {
      fetchMatches()
    } else {
      setMatches([])
      setIsDemoMatches(false)
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
      badge="Matcher Agent"
    >
      <MatchDashboard
        matches={matches}
        isLoading={isLoading}
        error={error}
        isDemoMatches={isDemoMatches}
        activeResume={activeResume}
        onRunMatch={fetchMatches}
        onStartCoaching={handleStartCoaching}
      />
    </PageContainer>
  )
}
