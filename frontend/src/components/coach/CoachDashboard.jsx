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
      <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-md">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex items-center gap-2 text-slate-300 text-xs font-semibold shrink-0">
                <Briefcase className="h-4 w-4 text-blue-400" />
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
                  className="w-full sm:max-w-md h-10 rounded-lg border border-slate-700 bg-slate-950 px-3 text-xs text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  {matchedJobs.map((j) => {
                    const id = j.job_id || j.id
                    return (
                      <option key={id} value={id}>
                        {j.title} — {j.company_name} ({j.location || "Remote"})
                      </option>
                    )
                  })}
                </select>
              ) : (
                <div className="text-xs text-slate-400 italic">
                  Run a match search in the "Job Matches" tab or load demo matches first.
                </div>
              )}
            </div>

            <Button
              variant="gradient"
              onClick={handleStartSession}
              disabled={isAnyLoading || !selectedJobId || !activeResume}
              className="shrink-0"
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
        <Card className="border-blue-500/30 bg-blue-950/20 text-blue-200 animate-pulse">
          <CardContent className="p-5 flex items-center gap-4">
            <Loader2 className="h-6 w-6 text-blue-400 animate-spin shrink-0" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-white">Step 1: Analyzing Skill Match</h4>
              <p className="text-xs text-blue-300/80">
                Comparing your resume against the selected role — computing gaps, strengths and readiness score…
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2 loading: question bank being generated by Ollama */}
      {!isLoading && isLoadingQuestions && gapReport && (
        <Card className="border-purple-500/30 bg-purple-950/20 text-purple-200">
          <CardContent className="p-5 flex items-center gap-4">
            <Loader2 className="h-6 w-6 text-purple-400 animate-spin shrink-0" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-white">
                Step 1 complete — generating question bank…
              </h4>
              <p className="text-xs text-purple-300/80">
                Ollama is crafting technical, behavioral and gap-probing questions tailored to your profile. Step 2 will appear in a few seconds.
              </p>
            </div>
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 ml-auto" title="Skill gap loaded" />
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-sm text-rose-300">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            <div>
              <span className="font-semibold">Coach Agent: </span>
              <span>{error}</span>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-rose-500/30 text-rose-200 hover:bg-rose-500/20 shrink-0"
            onClick={handleStartSession}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Main 3-Step Navigation Tabs */}
      <Tabs value={coachTab} onValueChange={setCoachTab}>
        <TabsList className="grid grid-cols-3 w-full sm:w-auto">
          <TabsTrigger value="gaps" className="text-xs">
            <Layers className="h-3.5 w-3.5 mr-1.5 text-blue-400" />
            Step 1: Skill Gap Diagnostic
          </TabsTrigger>
          <TabsTrigger value="questions" className="text-xs">
            <FileQuestion className="h-3.5 w-3.5 mr-1.5 text-purple-400" />
            Step 2: Curated Question Bank
            {isLoadingQuestions && (
              <Loader2 className="h-3 w-3 ml-1.5 animate-spin text-purple-400" />
            )}
          </TabsTrigger>
          <TabsTrigger value="terminal" className="text-xs">
            <Terminal className="h-3.5 w-3.5 mr-1.5 text-emerald-400" />
            Step 3: Mock Interview Terminal
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
            <Card className="border-slate-800 bg-slate-900/40">
              <CardContent className="p-8 flex flex-col items-center gap-4 text-center">
                <Loader2 className="h-8 w-8 text-purple-400 animate-spin" />
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">Generating Question Bank</h4>
                  <p className="text-xs text-slate-400">
                    Ollama is crafting tailored technical, behavioral, and gap-probing questions based on your skill analysis.
                    This takes about 8–15 seconds on a local model.
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
