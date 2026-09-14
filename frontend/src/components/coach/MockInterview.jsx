import React, { useState, useEffect } from "react"
import {
  Terminal,
  Send,
  Loader2,
  RefreshCw,
  Sparkles,
  HelpCircle,
  CheckCircle2,
  AlertCircle,
  MessageSquare,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { AnswerEvaluator } from "./AnswerEvaluator"

export function MockInterview({
  activeQuestion,
  jobContext = "Senior Backend Engineer",
  onEvaluateAnswer,
  isEvaluating,
  evaluationResult,
}) {
  const [currentAnswer, setCurrentAnswer] = useState("")
  const [errorMsg, setErrorMsg] = useState(null)

  useEffect(() => {
    // Reset answer when question changes
    setCurrentAnswer("")
    setErrorMsg(null)
  }, [activeQuestion])

  const defaultQuestion = {
    id: "DEMO-01",
    target_skill: "FastAPI / AsyncIO",
    difficulty: "senior",
    question:
      "Can you explain the event-loop architecture in Python FastAPI, and how you prevent worker thread starvation when dealing with heavy CPU tasks versus blocking I/O calls?",
    why_asked: "Tests understanding of asyncio execution loops and threading pool delegation.",
  }

  const question = activeQuestion || defaultQuestion

  const wordCount = currentAnswer.trim() ? currentAnswer.trim().split(/\s+/).length : 0

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!currentAnswer.trim()) {
      setErrorMsg("Please type your practice answer before submitting.")
      return
    }
    if (wordCount < 15) {
      setErrorMsg("Please provide a more detailed response (aim for at least 30-50 words).")
      return
    }

    setErrorMsg(null)
    if (onEvaluateAnswer) {
      await onEvaluateAnswer({
        questionId: question.id,
        questionText: question.question,
        targetSkill: question.target_skill || "General Engineering",
        jobContext,
        candidateAnswer: currentAnswer,
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Question Prompt Terminal Card */}
      <Card className="border-blue-500/40 bg-slate-950/80 shadow-2xl">
        <CardHeader className="p-4 border-b border-slate-800 bg-slate-900/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-blue-400" />
              <span className="text-xs font-mono font-bold text-slate-300">
                Interactive Mock Interview Terminal
              </span>
              <Badge variant="primary" className="text-[10px]">
                {question.target_skill}
              </Badge>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Target Role: {jobContext}</span>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          {/* Question Text Box */}
          <div className="space-y-2">
            <div className="text-[11px] font-mono uppercase tracking-wider text-blue-400 font-semibold">
              Interviewer Prompt ({question.id || "Question"}):
            </div>
            <h3 className="text-lg font-bold text-white leading-relaxed">{question.question}</h3>
            {question.why_asked && (
              <p className="text-xs text-slate-400 italic">Interviewer expectation: {question.why_asked}</p>
            )}
          </div>

          {/* Answer Input Area */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-semibold text-slate-300">Your Practice Answer:</span>
              <span className={`font-mono ${wordCount >= 40 ? "text-emerald-400" : "text-slate-400"}`}>
                Word count: {wordCount} (recommended: 60-150 words)
              </span>
            </div>

            <Textarea
              value={currentAnswer}
              onChange={(e) => setCurrentAnswer(e.target.value)}
              placeholder="Structure your answer clearly: state the direct solution, architectural trade-offs, and quantify your real-world experience (STAR method for behavioral)..."
              rows={6}
              disabled={isEvaluating}
              className="font-sans text-sm leading-relaxed p-4 bg-slate-900/90 border-slate-800 focus:border-blue-500"
            />

            {errorMsg && (
              <div className="flex items-center gap-2 text-xs text-rose-400">
                <AlertCircle className="h-3.5 w-3.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2 text-[11px] text-slate-400">
                <Sparkles className="h-3.5 w-3.5 text-blue-400" />
                <span>Evaluated across Technical Accuracy, Depth, STAR Structure, and Specificity.</span>
              </div>

              <Button
                type="submit"
                variant="gradient"
                disabled={isEvaluating || !currentAnswer.trim()}
                className="shrink-0"
              >
                {isEvaluating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    <span>Grading with Agent Rubrics...</span>
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-2" />
                    <span>Submit Answer for Evaluation</span>
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Real-time Rubric Evaluation Scorecard */}
      {evaluationResult && <AnswerEvaluator evaluation={evaluationResult} />}
    </div>
  )
}
