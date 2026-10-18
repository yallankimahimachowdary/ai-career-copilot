import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Briefcase,
  MapPin,
  DollarSign,
  GraduationCap,
  Sparkles,
  Award,
  Layers,
  BarChart2,
  CheckCircle2,
} from "lucide-react"
import { Dialog, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { CircularProgress } from "@/components/ui/progress"
import { ShapWaterfall } from "./ShapWaterfall"
import { SkillComparison } from "./SkillComparison"
import { ScoreBreakdown } from "./ScoreBreakdown"
import { formatCurrency, formatPercent } from "@/lib/utils"

export function MatchDetailModal({ match, resumeId, open, onOpenChange, onStartCoaching }) {
  const [activeTab, setActiveTab] = useState("shap")
  const navigate = useNavigate()

  if (!match) return null

  const fitPercent = Math.round((match.final_score || match.composite_score || 0) * 100)
  const skillsBreakdown = match.skills_breakdown || {}
  const features = match.features || {}
  const explanations = match.explanations || []

  const handleGoToCoach = () => {
    onOpenChange(false)
    if (onStartCoaching) {
      onStartCoaching(match)
    } else {
      navigate(`/coach?job_id=${match.job_id}`)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pr-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-bold text-[#7A2D4A] uppercase tracking-wider">
                Rank #{match.rank || 1} Recommendation
              </span>
              {match.remote_allowed && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                  Remote Allowed
                </span>
              )}
            </div>
            <DialogTitle>{match.title}</DialogTitle>
            <DialogDescription className="flex items-center gap-3 mt-1 text-[#5C5C7A]">
              <span className="text-[#7A2D4A] font-semibold">{match.company_name || "Not specified"}</span>
              <span className="flex items-center gap-1 text-[#5C5C7A]">
                <MapPin className="h-3 w-3" />
                {match.location || "Not specified"}
              </span>
              {match.work_type && <span className="text-[#5C5C7A]">• {match.work_type}</span>}
            </DialogDescription>
          </div>

          <div className="flex items-center gap-3">
            <CircularProgress
              value={fitPercent}
              size={64}
              strokeWidth={6}
              label={`${fitPercent}%`}
              sublabel="Fit Score"
              color={fitPercent >= 80 ? "#7A2D4A" : fitPercent >= 60 ? "#5C5C7A" : "#D97706"}
            />
          </div>
        </div>
      </DialogHeader>

      <div className="mt-6 space-y-6">
        {/* Model Ensemble Confidence Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-center">
            <span className="text-[11px] text-[#5C5C7A] block">Final Fit Score</span>
            <span className="text-lg font-bold text-[#7A2D4A] font-mono">
              {formatPercent(match.final_score)}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-center">
            <span className="text-[11px] text-[#5C5C7A] block">XGBoost ML Score</span>
            <span className="text-lg font-bold text-[#3A3A52] font-mono">
              {formatPercent(match.xgboost_score)}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-center">
            <span className="text-[11px] text-[#5C5C7A] block">Rule-Based Composite</span>
            <span className="text-lg font-bold text-[#3A3A52] font-mono">
              {formatPercent(match.composite_score)}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-[#EDE7F6] border border-[#DDD6E7] text-center">
            <span className="text-[11px] text-[#5C5C7A] block">Vector Semantic Sim</span>
            <span className="text-lg font-bold text-[#7A2D4A] font-mono">
              {formatPercent(match.semantic_score)}
            </span>
          </div>
        </div>

        {/* Tab Navigation inside Modal */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid grid-cols-3 w-full">
            <TabsTrigger value="shap" className="text-xs">
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
              SHAP Explainability (XAI)
            </TabsTrigger>
            <TabsTrigger value="skills" className="text-xs">
              <Layers className="h-3.5 w-3.5 mr-1.5" />
              Skills Diagnostics
            </TabsTrigger>
            <TabsTrigger value="features" className="text-xs">
              <BarChart2 className="h-3.5 w-3.5 mr-1.5" />
              Features & Deficits
            </TabsTrigger>
          </TabsList>

          <TabsContent value="shap" className="pt-2">
            <ShapWaterfall explanations={explanations} />
          </TabsContent>

          <TabsContent value="skills" className="pt-2">
            <SkillComparison skillsBreakdown={skillsBreakdown} />
          </TabsContent>

          <TabsContent value="features" className="pt-2 space-y-4">
            <ScoreBreakdown features={features} />

            <div className="p-4 rounded-xl bg-[#F5F0FB] border border-[#DDD6E7] text-xs space-y-2">
              <h4 className="font-semibold text-[#3A3A52]">Tabular Feature Vector Passed to XGBoost:</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 text-[#3A3A52] font-mono">
                <div>
                  <span className="text-[#5C5C7A] block">Candidate Experience:</span>
                  <span className="text-[#3A3A52] font-semibold">{features.candidate_years_experience || 0} yrs</span>
                </div>
                <div>
                  <span className="text-[#5C5C7A] block">Job Required Experience:</span>
                  <span className="text-[#3A3A52] font-semibold">{features.job_required_years || 0} yrs</span>
                </div>
                <div>
                  <span className="text-[#5C5C7A] block">Experience Deficit:</span>
                  <span className={features.experience_deficit > 0 ? "text-red-700 font-semibold" : "text-emerald-700 font-semibold"}>
                    {features.experience_deficit || 0} yrs
                  </span>
                </div>
                <div>
                  <span className="text-[#5C5C7A] block">Penalty Factor:</span>
                  <span className="text-amber-700 font-semibold">{features.experience_penalty || 0}</span>
                </div>
                <div>
                  <span className="text-[#5C5C7A] block">Title Overlap Score:</span>
                  <span className="text-[#7A2D4A] font-semibold">{formatPercent(features.title_similarity)}</span>
                </div>
                <div>
                  <span className="text-[#5C5C7A] block">Education Ordinal Level:</span>
                  <span className="text-[#3A3A52] font-semibold">{features.education_level_match || 1.0}</span>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Modal Action CTA */}
        <div className="pt-4 border-t border-[#DDD6E7] flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-[#5C5C7A]">
            Targeting this position? Practice tailored technical and behavioral questions.
          </p>
          <Button variant="default" onClick={handleGoToCoach} className="w-full sm:w-auto bg-[#7A2D4A] hover:bg-[#63233B] text-white">
            <GraduationCap className="h-4 w-4 mr-2" />
            Launch Interview Coach for this Role
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
