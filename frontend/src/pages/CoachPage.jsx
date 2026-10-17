import React, { useState, useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { PageContainer } from "@/components/layout/PageContainer"
import { CoachDashboard } from "@/components/coach/CoachDashboard"
import { coachApi } from "@/api/coachApi"
import { jobApi } from "@/api/jobApi"
import { matchApi } from "@/api/matchApi"
import { getCandidateDomainRole } from "@/pages/MarketPage"

export function CoachPage({ activeResume, targetJob }) {
  const [searchParams] = useSearchParams()
  const jobIdFromQuery = searchParams.get("job_id")
  const [jobsList, setJobsList] = useState([])
  const [selectedJobId, setSelectedJobId] = useState(
    jobIdFromQuery || targetJob?.job_id || targetJob?.id || null
  )

  // Progressive loading state
  const [gapReport, setGapReport] = useState(null)       // Step 1: instant deterministic
  const [questionBank, setQuestionBank] = useState(null)  // Step 2: Ollama async
  const [isLoadingGap, setIsLoadingGap] = useState(false)
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false)
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [evaluationResult, setEvaluationResult] = useState(null)
  const [error, setError] = useState(null)

  // Track the in-flight job so background QB doesn't overwrite a newer request
  const activeJobRef = useRef(null)

  // Fetch candidate-aware matched jobs from backend
  useEffect(() => {
    let isMounted = true
    const loadProfileAwareJobs = async () => {
      try {
        let jobs = []
        if (activeResume?.id) {
          try {
            const matchesResponse = await matchApi.matchJobsForResume(activeResume.id, { limit: 20 })
            const matches = matchesResponse?.matches || (Array.isArray(matchesResponse) ? matchesResponse : [])
            if (matches && matches.length > 0) {
              jobs = matches.map((m) => ({
                id: m.job_id || m.id,
                job_id: m.job_id || m.id,
                title: m.job_title || m.title,
                company_name: m.company_name,
                location: m.location,
                skills: m.skills_breakdown?.required_skills || m.skills || [],
                fit_score: m.final_score ? Math.round(m.final_score * 100) : undefined,
              }))
            }
          } catch (matchErr) {
            console.warn("Could not fetch profile matches, falling back to domain search:", matchErr)
          }
        }

        if (jobs.length === 0) {
          const domainRole = getCandidateDomainRole(activeResume)
          const domainJobs = await jobApi.listJobs({ limit: 20, title: domainRole })
          if (domainJobs && domainJobs.length > 0) {
            jobs = domainJobs
          } else {
            jobs = await jobApi.listJobs({ limit: 20 })
          }
        }

        if (isMounted && jobs && jobs.length > 0) {
          setJobsList(jobs)
          setSelectedJobId((currentId) => {
            if (currentId && jobs.some((j) => (j.job_id || j.id) === currentId)) {
              return currentId
            }
            return jobIdFromQuery || jobs[0].job_id || jobs[0].id
          })
        }
      } catch (e) {
        console.warn("Could not load jobs for coach:", e)
      }
    }
    loadProfileAwareJobs()
    return () => { isMounted = false }
  }, [activeResume?.id, jobIdFromQuery])

  // Sync when targetJob changes from outside (e.g. from Job Matches page)
  useEffect(() => {
    const externalId = jobIdFromQuery || targetJob?.job_id || targetJob?.id
    if (externalId) {
      setSelectedJobId(externalId)
    }
  }, [jobIdFromQuery, targetJob?.job_id, targetJob?.id])

  /**
   * Progressive 2-step generation:
   * 1. POST /coach/skill-gap  → deterministic, ~instant — renders Step 1 immediately
   * 2. POST /coach/question-bank → Ollama, ~8-15s — renders Step 2 when ready
   */
  const handleGenerateSession = async (jobId) => {
    if (!activeResume?.id || !jobId) return

    const thisJob = jobId
    activeJobRef.current = thisJob

    // Reset state for new generation
    setIsLoadingGap(true)
    setIsLoadingQuestions(false)
    setGapReport(null)
    setQuestionBank(null)
    setError(null)
    setEvaluationResult(null)

    // --- STEP 1: Deterministic skill-gap (instant) ---
    let gap
    try {
      gap = await coachApi.getSkillGapReport(activeResume.id, jobId)
      if (activeJobRef.current !== thisJob) return // stale, a newer job was selected
      if (activeResume.candidate_name && !gap.candidate_name) {
        gap.candidate_name = activeResume.candidate_name
      }
      setGapReport(gap)
    } catch (err) {
      if (activeJobRef.current !== thisJob) return
      console.warn("Skill-gap step failed:", err.message)
      setError(`Step 1 failed: ${err.message}. Click "Generate" to retry.`)
      setIsLoadingGap(false)
      return
    } finally {
      if (activeJobRef.current === thisJob) setIsLoadingGap(false)
    }

    // --- STEP 2: Question bank via Ollama (async, shown when ready) ---
    if (activeJobRef.current !== thisJob) return
    setIsLoadingQuestions(true)
    try {
      const qb = await coachApi.getQuestionBank(activeResume.id, jobId)
      if (activeJobRef.current !== thisJob) return
      setQuestionBank(qb)
    } catch (err) {
      if (activeJobRef.current !== thisJob) return
      console.warn("Question bank step failed, using fallback:", err.message)
      // Don't show a hard error — Step 1 is already rendered. Just note the issue.
      setError(`Questions couldn't load (${err.message}). Step 1 results are still available above.`)
    } finally {
      if (activeJobRef.current === thisJob) setIsLoadingQuestions(false)
    }
  }

  // Track whether the user has interacted (picked a job or clicked generate)
  const hasUserInteractedRef = useRef(Boolean(jobIdFromQuery || targetJob?.job_id || targetJob?.id))

  const handleSelectJob = (id) => {
    hasUserInteractedRef.current = true
    setSelectedJobId(id)
    handleGenerateSession(id)
  }

  // Trigger only if explicit targetJob/query param was provided or user already interacted
  useEffect(() => {
    if (activeResume?.id && selectedJobId && hasUserInteractedRef.current) {
      handleGenerateSession(selectedJobId)
    }
  }, [activeResume?.id, activeResume?.candidate_name])


  const handleEvaluateAnswer = async (payload) => {
    setIsEvaluating(true)
    setError(null)
    setEvaluationResult(null)
    try {
      const result = await coachApi.evaluateAnswer(payload)
      setEvaluationResult(result)
    } catch (err) {
      setError(`Answer evaluation failed: ${err.message}. Please click "Submit for Rubric Evaluation" to retry.`)
    } finally {
      setIsEvaluating(false)
    }
  }

  // Combine into a sessionData-compatible shape for CoachDashboard
  const sessionData = gapReport
    ? {
        skill_gap_report: gapReport,
        question_bank: questionBank,
        overall_readiness_score: gapReport.overall_readiness_score,
        top_preparation_priorities: gapReport.critical_gaps?.slice(0, 3).map((g) => g.recommendation) || [],
      }
    : null

  return (
    <PageContainer
      title="Interview Coach & Practice Terminal"
      badge="Coach Agent"
    >
      <CoachDashboard
        activeResume={activeResume}
        matchedJobs={jobsList}
        initialJobId={selectedJobId}
        onSelectJob={handleSelectJob}
        onGenerateSession={handleGenerateSession}
        onEvaluateAnswer={handleEvaluateAnswer}
        sessionData={sessionData}
        isLoading={isLoadingGap}
        isLoadingQuestions={isLoadingQuestions}
        isEvaluating={isEvaluating}
        evaluationResult={evaluationResult}
        error={error}
      />
    </PageContainer>
  )
}
