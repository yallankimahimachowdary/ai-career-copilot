import React, { useState } from "react"
import {
  Code2,
  Users,
  AlertCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  PlayCircle,
  Sparkles,
  Lightbulb,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

export function QuestionBank({ questionBank, onPracticeQuestion }) {
  const [activeTab, setActiveTab] = useState("technical")
  const [expandedAnswers, setExpandedAnswers] = useState({})

  if (!questionBank) {
    return (
      <div className="p-12 text-center text-xs text-slate-400 border border-slate-800 rounded-xl bg-slate-900/30">
        No question bank generated yet. Select a target job to fetch curated interview questions.
      </div>
    )
  }

  const technical = questionBank.technical_questions || []
  const behavioral = questionBank.behavioral_questions || []
  const gap = questionBank.gap_questions || []
  const tips = questionBank.preparation_tips || []

  const toggleAnswer = (id) => {
    setExpandedAnswers((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const renderQuestionCard = (q, index, typeIcon, typeColor) => {
    const isExpanded = !!expandedAnswers[q.id]
    const Icon = typeIcon

    return (
      <Card key={q.id || index} className="border-slate-800/80 bg-slate-900/60 hover:border-slate-700 transition-all">
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={`p-1.5 rounded-lg bg-${typeColor}-500/10 text-${typeColor}-400`}>
                <Icon className="h-4 w-4" />
              </span>
              <span className="font-mono text-xs font-bold text-slate-400">{q.id || `Q-${index + 1}`}</span>
              <Badge variant="outline" className="text-slate-300 capitalize text-[10px]">
                {q.difficulty || "Senior"} Level
              </Badge>
              {q.target_skill && (
                <Badge variant="primary" className="text-[10px]">
                  {q.target_skill}
                </Badge>
              )}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => onPracticeQuestion && onPracticeQuestion(q)}
              className="text-xs bg-blue-600/10 hover:bg-blue-600 hover:text-white text-blue-400 border-blue-500/30"
            >
              <PlayCircle className="h-3.5 w-3.5 mr-1" />
              Practice in Terminal
            </Button>
          </div>

          <div>
            <h4 className="text-base font-semibold text-white leading-relaxed">{q.question}</h4>
          </div>

          {q.why_asked && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-950/50 border border-slate-800/80 text-xs text-slate-300">
              <HelpCircle className="h-3.5 w-3.5 text-indigo-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-200">Interviewer Intent: </strong>
                <span>{q.why_asked}</span>
              </div>
            </div>
          )}

          {/* Sample Answer Collapsible */}
          {q.sample_answer && (
            <div className="pt-1">
              <button
                type="button"
                onClick={() => toggleAnswer(q.id)}
                className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium cursor-pointer"
              >
                <span>{isExpanded ? "Hide Model Response" : "Show Model Response & Rubrics"}</span>
                {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>

              {isExpanded && (
                <div className="mt-3 p-4 rounded-xl bg-slate-950/80 border border-blue-500/20 text-xs text-slate-300 space-y-3 animate-in fade-in duration-150">
                  <div>
                    <h5 className="font-semibold text-emerald-400 mb-1">Target Model Answer:</h5>
                    <p className="leading-relaxed text-slate-200">{q.sample_answer}</p>
                  </div>

                  {q.evaluation_criteria && q.evaluation_criteria.length > 0 && (
                    <div className="pt-2 border-t border-slate-800">
                      <h5 className="font-semibold text-slate-400 mb-1">Key Rubric Signals Looked For:</h5>
                      <ul className="list-disc list-inside space-y-1 text-slate-400">
                        {q.evaluation_criteria.map((crit, cIdx) => (
                          <li key={cIdx}>{crit}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Tab Navigation for Question Categories */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-3 w-full sm:w-auto">
          <TabsTrigger value="technical" className="text-xs">
            <Code2 className="h-3.5 w-3.5 mr-1.5 text-blue-400" />
            Technical Architecture ({technical.length})
          </TabsTrigger>
          <TabsTrigger value="behavioral" className="text-xs">
            <Users className="h-3.5 w-3.5 mr-1.5 text-purple-400" />
            STAR Behavioral ({behavioral.length})
          </TabsTrigger>
          <TabsTrigger value="gap" className="text-xs">
            <AlertCircle className="h-3.5 w-3.5 mr-1.5 text-rose-400" />
            Skill-Gap Probing ({gap.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="technical" className="space-y-4 pt-2">
          {technical.length > 0 ? (
            technical.map((q, idx) => renderQuestionCard(q, idx, Code2, "blue"))
          ) : (
            <p className="text-xs text-slate-400 italic">No technical questions generated.</p>
          )}
        </TabsContent>

        <TabsContent value="behavioral" className="space-y-4 pt-2">
          {behavioral.length > 0 ? (
            behavioral.map((q, idx) => renderQuestionCard(q, idx, Users, "purple"))
          ) : (
            <p className="text-xs text-slate-400 italic">No behavioral questions generated.</p>
          )}
        </TabsContent>

        <TabsContent value="gap" className="space-y-4 pt-2">
          {gap.length > 0 ? (
            gap.map((q, idx) => renderQuestionCard(q, idx, AlertCircle, "rose"))
          ) : (
            <p className="text-xs text-slate-400 italic">No gap-probing questions generated.</p>
          )}
        </TabsContent>
      </Tabs>

      {/* Preparation Tips Card */}
      {tips.length > 0 && (
        <Card className="border-indigo-500/30 bg-indigo-950/10">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2 text-indigo-300">
              <Lightbulb className="h-4 w-4 text-indigo-400" />
              Strategic Interview Execution Tips
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-xs text-slate-300">
              {tips.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-indigo-400 font-bold">•</span>
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
