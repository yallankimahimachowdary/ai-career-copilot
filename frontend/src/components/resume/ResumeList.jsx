import React from "react"
import { FileText, Trash2, Calendar, Check, Award } from "lucide-react"
import { formatDate, formatTitleCase } from "@/lib/utils"

export function ResumeList({ resumes = [], activeResumeId, onSelect, onDelete }) {
  if (!resumes || resumes.length === 0) {
    return (
      <div className="p-6 text-center border border-dashed border-[#DDD6E7] rounded-xl bg-white">
        <p className="text-xs text-[#5C5C7A]">No resumes uploaded yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
      {resumes.map((resume) => {
        const isActive = activeResumeId === resume.id
        return (
          <div
            key={resume.id}
            onClick={() => onSelect(resume)}
            className={`group flex items-center justify-between p-3.5 rounded-xl border transition-all duration-150 cursor-pointer ${
              isActive
                ? "bg-[#EDE7F6] border-[#7A2D4A] shadow-xs"
                : "bg-white border-[#DDD6E7] hover:bg-[#FAF7F3] hover:border-[#DDD6E7]"
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div
                className={`p-2 rounded-lg shrink-0 ${
                  isActive ? "bg-[#7A2D4A] text-white" : "bg-[#EDE7F6] text-[#3A3A52] group-hover:bg-[#7A2D4A] group-hover:text-white"
                }`}
              >
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[#3A3A52] truncate">
                    {resume.candidate_name ? formatTitleCase(resume.candidate_name) : resume.filename}
                  </span>
                  {isActive && (
                    <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-100 px-1.5 py-0.5 rounded-full border border-emerald-300">
                      <Check className="h-2.5 w-2.5" /> Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[11px] text-[#5C5C7A] mt-0.5">
                  <span className="flex items-center gap-1 truncate">
                    <Calendar className="h-3 w-3" />
                    {formatDate(resume.created_at)}
                  </span>
                  <span>•</span>
                  <span className="text-[#7A2D4A] font-mono font-medium">
                    {resume.skills_count || resume.parsed_data?.skills?.length || 0} skills
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {onDelete && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm(`Delete resume ${resume.candidate_name || resume.filename}?`)) {
                      onDelete(resume.id)
                    }
                  }}
                  className="p-1.5 rounded-lg text-[#5C5C7A] hover:text-red-700 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                  title="Delete resume"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
