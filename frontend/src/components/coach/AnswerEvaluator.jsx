import React from "react"
import {
  Award,
  CheckCircle,
  AlertTriangle,
  Sparkles,
  BarChart,
  BookOpen,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"

export function AnswerEvaluator({ evaluation }) {
  if (!evaluation) return null

  const { score = 0, grade = "good", strengths = [], weaknesses = [], improved_answer, rubric_breakdown = {} } = evaluation

  const getGradeBadge = (g) => {
    switch (g?.toLowerCase()) {
      case "excellent":
        return { label: "Excellent Answer", variant: "success" }
      case "good":
        return { label: "Strong Foundation", variant: "primary" }
      case "needs_improvement":
        return { label: "Needs More Depth", variant: "warning" }
      default:
        return { label: "Underdeveloped", variant: "danger" }
    }
  }

  const badge = getGradeBadge(grade)

  return (
    <Card className="border-blue-500/30 bg-slate-900/90 shadow-2xl space-y-4 animate-in fade-in duration-300">
      <CardHeader className="pb-3 border-b border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-lg font-mono">
              {score.toFixed(1)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Coach Evaluation Scorecard</CardTitle>
                <Badge variant={badge.variant} className="text-[10px]">
                  {badge.label}
                </Badge>
              </div>
              <p className="text-xs text-slate-400">Score computed across 4 core engineering interview rubrics</p>
            </div>
          </div>
          <div className="text-xs font-mono text-slate-400">Scale: 0.0 - 10.0</div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-2">
        {/* Rubric Breakdown Progress Bars */}
        {Object.keys(rubric_breakdown).length > 0 && (
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
            <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-2">
              <BarChart className="h-3.5 w-3.5 text-blue-400" />
              Rubric Dimension Breakdown
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              {Object.entries(rubric_breakdown).map(([dim, val]) => (
                <div key={dim} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-400 capitalize">{dim.replace(/_/g, " ")}</span>
                    <span className="font-mono text-blue-400 font-bold">{val.toFixed(1)} / 10</span>
                  </div>
                  <Progress value={val} max={10} indicatorClassName="bg-blue-500" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strengths & Weaknesses Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Strengths */}
          <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/20 space-y-2">
            <h4 className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5" />
              Observed Strengths
            </h4>
            <ul className="space-y-1.5 text-xs text-slate-300">
              {strengths.map((str, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-emerald-400">•</span>
                  <span>{str}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Weaknesses / Suggestions */}
          <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/20 space-y-2">
            <h4 className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" />
              Areas for Improvement
            </h4>
            <ul className="space-y-1.5 text-xs text-slate-300">
              {weaknesses.map((w, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-amber-400">•</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Improved Model Answer */}
        {improved_answer && (
          <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-500/30 space-y-2">
            <h4 className="text-xs font-semibold text-blue-300 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-blue-400" />
              How to Elevate This Answer (Model Response):
            </h4>
            <p className="text-xs text-slate-200 leading-relaxed font-sans">{improved_answer}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
