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
  onGenerateSession,
  onEvaluateAnswer,
  sessionData,
  isLoading,
  isEvaluating,
  evaluationResult,
  error,
}) {
  const [selectedJobId, setSelectedJobId] = useState(initialJobId || matchedJobs[0]?.job_id || matchedJobs[0]?.id || "")
  const [coachTab, setCoachTab] = useState("gaps")
  const [activePracticeQuestion, setActivePracticeQuestion] = useState(null)

  useEffect(() => {
    if (initialJobId) {
      setSelectedJobId(initialJobId)
    } else if (!selectedJobId && matchedJobs.length > 0) {
      setSelectedJobId(matchedJobs[0].job_id || matchedJobs[0].id)
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
                  onChange={(e) => setSelectedJobId(e.target.value)}
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
              disabled={isLoading || !selectedJobId || !activeResume}
              className="shrink-0"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Synthesizing Coaching Pipeline...</span>
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

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-sm text-rose-300">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          <div>
            <span className="font-semibold">Coach Agent Error: </span>
            <span>{error}</span>
          </div>
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
          </TabsTrigger>
          <TabsTrigger value="terminal" className="text-xs">
            <Terminal className="h-3.5 w-3.5 mr-1.5 text-emerald-400" />
            Step 3: Mock Interview Terminal
          </TabsTrigger>
        </TabsList>

        <TabsContent value="gaps" className="pt-2">
          <SkillGapReport
            report={sessionData?.skill_gap_report}
            activeResume={activeResume}
            onProceedToQuestions={() => setCoachTab("questions")}
          />
        </TabsContent>

        <TabsContent value="questions" className="pt-2">
          <QuestionBank
            questionBank={sessionData?.question_bank}
            onPracticeQuestion={handlePracticeQuestion}
          />
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
