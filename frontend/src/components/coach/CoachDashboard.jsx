import React, { useState, useEffect } from "react"
import {
  GraduationCap,
  Sparkles,
  Layers,
  Terminal,
  FileQuestion,
  Loader2,
  AlertCircle,
  Briefcase,
  CheckCircle2,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { SkillGapReport } from "./SkillGapReport"
import { QuestionBank } from "./QuestionBank"
import { MockInterview } from "./MockInterview"

export function CoachDashboard({
  activeResume,
  matchedJobs = [],
  initialJobId,
  onSelectJob,
  onGenerateSession,
  onEvaluateAnswer,
  sessionData,
  isLoading,
  isLoadingQuestions,
  isEvaluating,
  evaluationResult,
  error,
}) {
  const [selectedJobId, setSelectedJobId] = useState(
    initialJobId || matchedJobs[0]?.job_id || matchedJobs[0]?.id || ""
  )
  const [coachTab, setCoachTab] = useState("gaps")
  const [activePracticeQuestion, setActivePracticeQuestion] = useState(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useEffect(() => {
    let timer
    if (isLoadingQuestions) {
      setElapsedSeconds(0)
      timer = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
    } else {
      setElapsedSeconds(0)
    }
    return () => clearInterval(timer)
  }, [isLoadingQuestions])

  useEffect(() => {
    if (initialJobId && matchedJobs.some((j) => (j.job_id || j.id) === initialJobId)) {
      setSelectedJobId(initialJobId)
    } else if (matchedJobs.length > 0) {
      const matchExists = matchedJobs.some((j) => (j.job_id || j.id) === selectedJobId)
      if (!matchExists) {
        const fallbackId = matchedJobs[0].job_id || matchedJobs[0].id
        setSelectedJobId(fallbackId)
        if (onSelectJob) onSelectJob(fallbackId)
      }
    }
  }, [initialJobId, matchedJobs])

  const selectedJob = matchedJobs.find((j) => (j.job_id || j.id) === selectedJobId)

  const handleStartSession = () => {
    if (onGenerateSession && selectedJobId) {
      onGenerateSession(selectedJobId)
    }
  }

  const handlePracticeQuestion = (question) => {
    setActivePracticeQuestion(question)
    setCoachTab("terminal")
  }

  const isAnyLoading = isLoading || isLoadingQuestions
  const gapReport = sessionData?.skill_gap_report
  const questionBank = sessionData?.question_bank

  return (
    <div className="space-y-6">
      {/* Top Target Role Selector & Action Card */}
      <Card className="border-[#DDD6E7] bg-white shadow-sm">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex items-center gap-2 text-[#3A3A52] text-xs font-semibold shrink-0">
                <Briefcase className="h-4 w-4 text-[#7A2D4A]" />
                <span>Target Job Posting:</span>
              </div>

              {matchedJobs.length > 0 ? (
                <select
                  value={selectedJobId}
                  onChange={(e) => {
                    const val = e.target.value
                    setSelectedJobId(val)
                    if (onSelectJob) onSelectJob(val)
                  }}
                  className="w-full sm:max-w-md h-10 rounded-lg border border-[#DDD6E7] bg-white px-3 text-xs text-[#3A3A52] focus:ring-2 focus:ring-[#7A2D4A] focus:outline-none"
                >
                  {matchedJobs.map((j) => {
                    const id = j.job_id || j.id
                    return (
                      <option key={id} value={id}>
                        {j.title} — {j.company_name || "Company Not Specified"} ({j.location || "Location Not Specified"})
                      </option>
                    )
                  })}
                </select>
              ) : (
                <div className="text-xs text-[#5C5C7A] italic">
                  Run a match search in the "Job Matches" tab or load demo matches first.
                </div>
              )}
            </div>

            <Button
              variant="default"
              onClick={handleStartSession}
              disabled={isAnyLoading || !selectedJobId || !activeResume}
              className="shrink-0 bg-[#7A2D4A] hover:bg-[#63233B] text-white"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Analyzing Skills...</span>
                </>
              ) : isLoadingQuestions ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Generating Questions...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  <span>Generate Full Coaching Session</span>
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Step 1 loading: skill gap analysis in progress */}
      {isLoading && (
        <Card className="border-[#DDD6E7] bg-[#EDE7F6] text-[#3A3A52] animate-pulse">
          <CardContent className="p-5 flex items-center gap-4">
            <Loader2 className="h-6 w-6 text-[#7A2D4A] animate-spin shrink-0" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-[#3A3A52]">Step 1: Analyzing Skill Match</h4>
              <p className="text-xs text-[#5C5C7A]">
                Comparing your resume against the selected role — computing gaps, strengths and readiness score…
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2 loading: question bank being generated by Ollama */}
      {!isLoading && isLoadingQuestions && gapReport && (
        <Card className="border-[#DDD6E7] bg-[#EDE7F6]/60 text-[#3A3A52]">
          <CardContent className="p-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 text-[#7A2D4A] animate-spin shrink-0" />
              <div>
                <h4 className="text-xs font-semibold text-[#3A3A52]">
                  Generating tailored questions with local Ollama ({elapsedSeconds}s elapsed)...
                </h4>
                <p className="text-[11px] text-[#5C5C7A]">
                  Generating questions, this can take up to a minute on local Ollama. Step 1 diagnostic is ready below.
                </p>
              </div>
            </div>
            <span className="text-[11px] font-mono text-[#7A2D4A] bg-white border border-[#DDD6E7] px-2 py-0.5 rounded-full shrink-0">
              {elapsedSeconds}s
            </span>
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <div>
              <span className="font-semibold">Coach Agent: </span>
              <span>{error}</span>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
            onClick={handleStartSession}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Main Navigation Tabs */}
      <Tabs value={coachTab} onValueChange={setCoachTab}>
        <TabsList className="grid grid-cols-3 w-full sm:w-auto">
          <TabsTrigger value="gaps" className="text-xs">
            <Layers className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Skill Gap Diagnostic
          </TabsTrigger>
          <TabsTrigger value="questions" className="text-xs">
            <FileQuestion className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Curated Question Bank
            {isLoadingQuestions && (
              <Loader2 className="h-3 w-3 ml-1.5 animate-spin text-[#7A2D4A]" />
            )}
          </TabsTrigger>
          <TabsTrigger value="terminal" className="text-xs">
            <Terminal className="h-3.5 w-3.5 mr-1.5 text-emerald-600" />
            Mock Interview Terminal
          </TabsTrigger>
        </TabsList>

        <TabsContent value="gaps" className="pt-2">
          <SkillGapReport
            report={gapReport}
            activeResume={activeResume}
            onProceedToQuestions={() => setCoachTab("questions")}
          />
        </TabsContent>

        <TabsContent value="questions" className="pt-2">
          {isLoadingQuestions && !questionBank ? (
            <Card className="border-[#DDD6E7] bg-white">
              <CardContent className="p-8 flex flex-col items-center gap-3 text-center">
                <Loader2 className="h-8 w-8 text-[#7A2D4A] animate-spin" />
                <div>
                  <h4 className="text-sm font-semibold text-[#3A3A52] mb-1">
                    Generating Question Bank ({elapsedSeconds}s elapsed)
                  </h4>
                  <p className="text-xs text-[#5C5C7A] max-w-md mx-auto">
                    Generating questions, this can take up to a minute on local Ollama. We're creating tailored technical, behavioral, and gap-probing questions.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <QuestionBank
              questionBank={questionBank}
              onPracticeQuestion={handlePracticeQuestion}
            />
          )}
        </TabsContent>

        <TabsContent value="terminal" className="pt-2">
          <MockInterview
            activeQuestion={activePracticeQuestion}
            jobContext={selectedJob?.title || "Senior Software Engineer"}
            onEvaluateAnswer={onEvaluateAnswer}
            isEvaluating={isEvaluating}
            evaluationResult={evaluationResult}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
