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
      <div className="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-200 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800">
          <CheckCircle className="h-4 w-4 shrink-0 text-emerald-700" />
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
          <p className="text-xs text-[#5C5C7A] italic">No direct required skill matches</p>
        )}
      </div>

      {/* Critical Missing Skills */}
      {missingMustHave.length > 0 && (
        <div className="p-3.5 rounded-xl bg-red-50/60 border border-red-200 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-red-700">
            <XCircle className="h-4 w-4 shrink-0 text-red-700" />
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
        <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-800">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" />
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
