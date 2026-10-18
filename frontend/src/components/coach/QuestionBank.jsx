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
      <div className="p-12 text-center text-xs text-[#5C5C7A] border border-[#DDD6E7] rounded-xl bg-white">
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
      <Card key={q.id || index} className="border-[#DDD6E7] bg-white hover:border-[#7A2D4A]/40 transition-all shadow-sm">
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-[#EDE7F6] text-[#7A2D4A]">
                <Icon className="h-4 w-4" />
              </span>
              <span className="font-mono text-xs font-bold text-[#5C5C7A]">{q.id || `Q-${index + 1}`}</span>
              <Badge variant="outline" className="text-[#5C5C7A] capitalize text-[10px] border-[#DDD6E7]">
                {q.difficulty || "Senior"} Level
              </Badge>
              {q.target_skill && (
                <Badge variant="primary" className="text-[10px]">
                  {q.target_skill}
                </Badge>
              )}
              {(q.source || q.origin) && (
                <Badge
                  variant="outline"
                  className={`text-[10px] ${
                    q.source === "retrieved" || q.origin === "retrieved"
                      ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                      : "bg-amber-50 text-amber-800 border-amber-300"
                  }`}
                >
                  {q.source === "retrieved" || q.origin === "retrieved"
                    ? "Corpus Retrieved"
                    : "Rule-Based Fallback"}
                </Badge>
              )}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => onPracticeQuestion && onPracticeQuestion(q)}
              className="text-xs bg-[#EDE7F6] hover:bg-[#7A2D4A] hover:text-white text-[#7A2D4A] border border-[#DDD6E7]"
            >
              <PlayCircle className="h-3.5 w-3.5 mr-1" />
              Practice in Terminal
            </Button>
          </div>

          <div>
            <h4 className="text-base font-semibold text-[#3A3A52] leading-relaxed">{q.question}</h4>
          </div>

          {q.why_asked && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-[#FAF7F3] border border-[#DDD6E7] text-xs text-[#5C5C7A]">
              <HelpCircle className="h-3.5 w-3.5 text-[#7A2D4A] shrink-0 mt-0.5" />
              <div>
                <strong className="text-[#3A3A52]">Interviewer Intent: </strong>
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
                className="flex items-center gap-1.5 text-xs text-[#7A2D4A] hover:text-[#63233B] font-medium cursor-pointer"
              >
                <span>{isExpanded ? "Hide Model Response" : "Show Model Response & Rubrics"}</span>
                {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>

              {isExpanded && (
                <div className="mt-3 p-4 rounded-xl bg-[#F5F0FB] border border-[#DDD6E7] text-xs text-[#3A3A52] space-y-3 animate-in fade-in duration-150">
                  <div>
                    <h5 className="font-semibold text-emerald-800 mb-1">Target Model Answer:</h5>
                    <p className="leading-relaxed text-[#3A3A52]">{q.sample_answer}</p>
                  </div>

                  {q.evaluation_criteria && q.evaluation_criteria.length > 0 && (
                    <div className="pt-2 border-t border-[#DDD6E7]">
                      <h5 className="font-semibold text-[#5C5C7A] mb-1">Key Rubric Signals Looked For:</h5>
                      <ul className="list-disc list-inside space-y-1 text-[#5C5C7A]">
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
            <Code2 className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Technical Architecture ({technical.length})
          </TabsTrigger>
          <TabsTrigger value="behavioral" className="text-xs">
            <Users className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            STAR Behavioral ({behavioral.length})
          </TabsTrigger>
          <TabsTrigger value="gap" className="text-xs">
            <AlertCircle className="h-3.5 w-3.5 mr-1.5 text-red-600" />
            Skill-Gap Probing ({gap.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="technical" className="space-y-4 pt-2">
          {technical.length > 0 ? (
            technical.map((q, idx) => renderQuestionCard(q, idx, Code2, "burgundy"))
          ) : (
            <p className="text-xs text-[#5C5C7A] italic">No technical questions generated.</p>
          )}
        </TabsContent>

        <TabsContent value="behavioral" className="space-y-4 pt-2">
          {behavioral.length > 0 ? (
            behavioral.map((q, idx) => renderQuestionCard(q, idx, Users, "burgundy"))
          ) : (
            <p className="text-xs text-[#5C5C7A] italic">No behavioral questions generated.</p>
          )}
        </TabsContent>

        <TabsContent value="gap" className="space-y-4 pt-2">
          {gap.length > 0 ? (
            gap.map((q, idx) => renderQuestionCard(q, idx, AlertCircle, "red"))
          ) : (
            <p className="text-xs text-[#5C5C7A] italic">No gap-probing questions generated.</p>
          )}
        </TabsContent>
      </Tabs>

      {/* Preparation Tips Card */}
      {tips.length > 0 && (
        <Card className="border-[#DDD6E7] bg-[#EDE7F6]">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2 text-[#7A2D4A]">
              <Lightbulb className="h-4 w-4 text-[#7A2D4A]" />
              Strategic Interview Execution Tips
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-xs text-[#3A3A52]">
              {tips.map((tip, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-[#7A2D4A] font-bold">•</span>
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
