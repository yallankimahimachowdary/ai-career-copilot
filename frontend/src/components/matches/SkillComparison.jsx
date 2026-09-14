import React from "react"
import { CheckCircle, AlertTriangle, XCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export function SkillComparison({ skillsBreakdown = {} }) {
  const matched = skillsBreakdown.matched_skills || []
  const missingMustHave = skillsBreakdown.missing_must_have || []
  const missingNiceToHave = skillsBreakdown.missing_nice_to_have || []

  return (
    <div className="space-y-4">
      {/* Matched Skills */}
      <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
          <CheckCircle className="h-4 w-4 shrink-0" />
          <span>Matched Qualifications ({matched.length})</span>
        </div>
        {matched.length > 0 ? (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {matched.map((skill, idx) => (
              <Badge key={idx} variant="success">
                {skill}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 italic">No direct required skill matches</p>
        )}
      </div>

      {/* Critical Missing Skills */}
      {missingMustHave.length > 0 && (
        <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/20 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-rose-400">
            <XCircle className="h-4 w-4 shrink-0" />
            <span>Missing Must-Have Skills ({missingMustHave.length})</span>
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {missingMustHave.map((skill, idx) => (
              <Badge key={idx} variant="danger">
                {skill}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Missing Nice-to-Have Skills */}
      {missingNiceToHave.length > 0 && (
        <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/20 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>Secondary / Nice-to-Have Gaps ({missingNiceToHave.length})</span>
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {missingNiceToHave.map((skill, idx) => (
              <Badge key={idx} variant="warning">
                {skill}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
