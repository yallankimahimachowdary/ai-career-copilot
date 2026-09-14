import React from "react"
import { FileText, Trash2, Calendar, Check, Award } from "lucide-react"
import { formatDate } from "@/lib/utils"

export function ResumeList({ resumes = [], activeResumeId, onSelect, onDelete }) {
  if (!resumes || resumes.length === 0) {
    return (
      <div className="p-6 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/20">
        <p className="text-xs text-slate-400">No resumes uploaded yet.</p>
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
                ? "bg-blue-600/10 border-blue-500/50 shadow-md shadow-blue-950/40"
                : "bg-slate-900/40 border-slate-800/80 hover:bg-slate-900/80 hover:border-slate-700"
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <div
                className={`p-2 rounded-lg shrink-0 ${
                  isActive ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 group-hover:text-white"
                }`}
              >
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white truncate">
                    {resume.candidate_name || resume.filename}
                  </span>
                  {isActive && (
                    <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.2 rounded-full border border-emerald-500/30">
                      <Check className="h-2.5 w-2.5" /> Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-0.5">
                  <span className="flex items-center gap-1 truncate">
                    <Calendar className="h-3 w-3" />
                    {formatDate(resume.created_at)}
                  </span>
                  <span>•</span>
                  <span className="text-blue-400 font-mono">
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
                  className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
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
