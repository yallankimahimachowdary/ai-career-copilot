import React, { useState } from "react"
import {
  Mail,
  Phone,
  MapPin,
  Globe,
  Briefcase,
  GraduationCap,
  FolderGit2,
  Award,
  Sparkles,
  CheckCircle2,
  Plus,
  UserCheck,
  Edit3,
  X,
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { SkillBadges } from "./SkillBadges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { formatTitleCase } from "@/lib/utils"

function LinkedinIcon({ className = "h-3.5 w-3.5" }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.45a1.64 1.64 0 1 0 0 3.28 1.64 1.64 0 0 0 0-3.28Z" />
    </svg>
  )
}

function GithubIcon({ className = "h-3.5 w-3.5" }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2Z" />
    </svg>
  )
}

export function ResumeProfileCard({ resume, onUpdateResume }) {
  const [newSkillText, setNewSkillText] = useState("")
  const [isEditingSummary, setIsEditingSummary] = useState(false)
  const [customSummary, setCustomSummary] = useState("")

  if (!resume || !resume.parsed_data) {
    return (
      <div className="flex flex-col items-center justify-center p-12 border border-[#DDD6E7] rounded-2xl bg-white text-center space-y-3 shadow-xs">
        <Sparkles className="h-10 w-10 text-[#7A2D4A] animate-pulse" />
        <p className="text-sm text-[#5C5C7A]">Select or upload a resume to view extracted profile entities.</p>
      </div>
    )
  }

  const { parsed_data } = resume
  const contact = parsed_data.contact_info || {}
  const extractedSkills = parsed_data.skills || []
  const manualSkills = resume.manual_skills || []
  const experience = (parsed_data.experience || []).filter(
    (exp) => (exp.title && exp.title.trim()) || (exp.company && exp.company.trim())
  )
  const education = parsed_data.education || []
  const projects = parsed_data.projects || []
  const certifications = parsed_data.certifications || []

  const currentSummary =
    resume.edited_summary !== undefined ? resume.edited_summary : parsed_data.summary

  const handleAddManualSkill = (e) => {
    e.preventDefault()
    const clean = newSkillText.trim()
    if (!clean) return
    if (extractedSkills.includes(clean) || manualSkills.includes(clean)) {
      setNewSkillText("")
      return
    }
    const updatedManual = [...manualSkills, clean]
    if (onUpdateResume) {
      onUpdateResume({
        ...resume,
        manual_skills: updatedManual,
        skills_count: extractedSkills.length + updatedManual.length,
      })
    }
    setNewSkillText("")
  }

  const handleRemoveManualSkill = (skillToRemove) => {
    const updatedManual = manualSkills.filter((s) => s !== skillToRemove)
    if (onUpdateResume) {
      onUpdateResume({
        ...resume,
        manual_skills: updatedManual,
        skills_count: extractedSkills.length + updatedManual.length,
      })
    }
  }

  const handleSaveSummary = () => {
    if (onUpdateResume) {
      onUpdateResume({
        ...resume,
        edited_summary: customSummary,
      })
    }
    setIsEditingSummary(false)
  }

  return (
    <div className="space-y-6">
      {/* Top Profile Summary Header Card */}
      <Card className="border-[#DDD6E7] bg-[#EDE7F6] shadow-xs">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-[#3A3A52] tracking-tight">
                  {contact.name || resume.candidate_name
                    ? formatTitleCase(contact.name || resume.candidate_name)
                    : "Candidate Profile"}
                </h2>
                <Badge variant="primary" className="font-mono text-[11px] whitespace-nowrap shrink-0">
                  Parsed by Agent
                </Badge>
                {resume.isDemo && (
                  <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded font-bold uppercase tracking-wider shrink-0">
                    Demo Data
                  </span>
                )}
              </div>

              {/* Contact Chips */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#5C5C7A] pt-1">
                {contact.email && (
                  <a
                    href={`mailto:${contact.email}`}
                    className="flex items-center gap-1.5 hover:text-[#7A2D4A] transition-colors"
                  >
                    <Mail className="h-3.5 w-3.5 text-[#7A2D4A]" />
                    <span>{contact.email}</span>
                  </a>
                )}
                {contact.phone && (
                  <span className="flex items-center gap-1.5 text-[#5C5C7A]">
                    <Phone className="h-3.5 w-3.5 text-[#5C5C7A]" />
                    <span>{contact.phone}</span>
                  </span>
                )}
                {contact.location && (
                  <span className="flex items-center gap-1.5 text-[#5C5C7A]">
                    <MapPin className="h-3.5 w-3.5 text-[#5C5C7A]" />
                    <span>{contact.location}</span>
                  </span>
                )}
              </div>

              {/* Social / Portfolio Links */}
              <div className="flex flex-wrap items-center gap-2 pt-2">
                {contact.linkedin_url && (
                  <a
                    href={contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white hover:bg-[#FAF7F3] text-xs text-[#3A3A52] transition-colors border border-[#DDD6E7]"
                  >
                    <LinkedinIcon className="h-3.5 w-3.5 text-[#7A2D4A]" />
                    <span>LinkedIn</span>
                  </a>
                )}
                {contact.github_url && (
                  <a
                    href={contact.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white hover:bg-[#FAF7F3] text-xs text-[#3A3A52] transition-colors border border-[#DDD6E7]"
                  >
                    <GithubIcon className="h-3.5 w-3.5 text-[#3A3A52]" />
                    <span>GitHub</span>
                  </a>
                )}
                {contact.portfolio_url && (
                  <a
                    href={contact.portfolio_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white hover:bg-[#FAF7F3] text-xs text-[#3A3A52] transition-colors border border-[#DDD6E7]"
                  >
                    <Globe className="h-3.5 w-3.5 text-emerald-700" />
                    <span>Portfolio</span>
                  </a>
                )}
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="flex sm:flex-col gap-2 shrink-0">
              <div className="rounded-xl bg-white p-3 border border-[#DDD6E7] text-center min-w-[110px] shadow-xs">
                <div className="text-xl font-bold text-[#7A2D4A]">
                  {extractedSkills.length + manualSkills.length}
                </div>
                <div className="text-[11px] text-[#5C5C7A] uppercase tracking-wider">Total Skills</div>
              </div>
              <div className="rounded-xl bg-white p-3 border border-[#DDD6E7] text-center min-w-[110px] shadow-xs">
                <div className="text-xl font-bold text-emerald-800">{experience.length}</div>
                <div className="text-[11px] text-[#5C5C7A] uppercase tracking-wider">Experience Roles</div>
              </div>
            </div>
          </div>

          {/* Professional Summary with Provenance Indicator */}
          {currentSummary && (
            <div className="mt-5 pt-4 border-t border-[#DDD6E7] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-semibold text-[#5C5C7A] uppercase tracking-wider">
                    Professional Summary
                  </h4>
                  {resume.edited_summary !== undefined ? (
                    <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-300">
                      <UserCheck className="h-3 w-3 mr-1" />
                      Candidate Edited
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px] bg-[#EDE7F6] text-[#7A2D4A] border-[#DDD6E7]">
                      <Sparkles className="h-3 w-3 mr-1" />
                      AI Extracted
                    </Badge>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setCustomSummary(currentSummary)
                    setIsEditingSummary(!isEditingSummary)
                  }}
                  className="text-xs text-[#7A2D4A] hover:underline flex items-center gap-1"
                >
                  <Edit3 className="h-3 w-3" />
                  <span>{isEditingSummary ? "Cancel" : "Edit"}</span>
                </button>
              </div>

              {isEditingSummary ? (
                <div className="space-y-2 pt-1">
                  <textarea
                    value={customSummary}
                    onChange={(e) => setCustomSummary(e.target.value)}
                    rows={3}
                    className="w-full text-xs p-2.5 rounded-lg border border-[#DDD6E7] bg-white text-[#3A3A52] focus:ring-1 focus:ring-[#7A2D4A] focus:outline-none"
                  />
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setIsEditingSummary(false)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={handleSaveSummary} className="bg-[#7A2D4A] text-white">
                      Save Summary
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[#3A3A52] leading-relaxed">{currentSummary}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Skills Section with Clear Distinction between Extracted vs User Edited */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#7A2D4A]" />
                Technical Skills & Tools ({extractedSkills.length + manualSkills.length})
              </CardTitle>
              <p className="text-xs text-[#5C5C7A] mt-0.5">
                AI extracted skills from document and candidate-verified additions
              </p>
            </div>

            {/* Form to Add Verified Skill */}
            <form onSubmit={handleAddManualSkill} className="flex items-center gap-2">
              <Input
                placeholder="Add custom skill..."
                value={newSkillText}
                onChange={(e) => setNewSkillText(e.target.value)}
                className="h-8 text-xs max-w-[160px] sm:max-w-[200px]"
              />
              <Button type="submit" size="sm" variant="secondary" className="h-8 text-xs text-[#7A2D4A]">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add
              </Button>
            </form>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* AI Extracted Skills */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#5C5C7A]">
                AI-Extracted Skills ({extractedSkills.length})
              </span>
              <span className="text-[10px] bg-[#EDE7F6] text-[#7A2D4A] px-2 py-0.5 rounded font-mono font-medium border border-[#DDD6E7]">
                Verified by Parser Agent
              </span>
            </div>
            <SkillBadges skills={extractedSkills} />
          </div>

          {/* Manually Added Skills */}
          {manualSkills.length > 0 && (
            <div className="space-y-2 pt-3 border-t border-[#E5E3EB]">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#7A2D4A]">
                  Manually Added by Candidate ({manualSkills.length})
                </span>
                <span className="text-[10px] bg-amber-50 text-amber-800 px-2 py-0.5 rounded font-mono font-medium border border-amber-200">
                  User Verified
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {manualSkills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#F9EBF0] text-[#7A2D4A] border border-[#DDD6E7]"
                  >
                    <span>{skill}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveManualSkill(skill)}
                      className="hover:text-red-700 focus:outline-none"
                      title="Remove manual skill"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Experience Timeline */}
      {experience.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-[#7A2D4A]" />
              Work Experience ({experience.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {experience.map((exp, idx) => (
              <div key={idx} className="relative pl-6 border-l-2 border-[#DDD6E7] space-y-2">
                <div className="absolute -left-[9px] top-1 h-4 w-4 rounded-full bg-white border-2 border-[#7A2D4A]" />
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div>
                    <h4 className="text-base font-semibold text-[#3A3A52]">{exp.title}</h4>
                    <p className="text-sm text-[#7A2D4A] font-medium">{exp.company}</p>
                  </div>
                  <div className="text-xs text-[#5C5C7A] font-mono">
                    {exp.start_date || "N/A"} — {exp.is_current ? "Present" : exp.end_date || "N/A"}
                    {exp.location && ` • ${exp.location}`}
                  </div>
                </div>

                {exp.description && (
                  Array.isArray(exp.description) ? (
                    exp.description.length > 0 && (
                      <ul className="space-y-1.5 pt-1 text-sm text-[#3A3A52] list-disc list-outside pl-4">
                        {exp.description.map((bullet, bIdx) => (
                          <li key={bIdx} className="leading-relaxed">
                            {bullet}
                          </li>
                        ))}
                      </ul>
                    )
                  ) : (
                    <p className="pt-1 text-sm text-[#3A3A52] leading-relaxed">
                      {String(exp.description)}
                    </p>
                  )
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Projects & Education Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Education */}
        {education.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-[#7A2D4A]" />
                Education ({education.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {education.map((edu, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] space-y-1">
                  <h4 className="text-sm font-semibold text-[#3A3A52]">{edu.institution}</h4>
                  <p className="text-xs text-[#5C5C7A] font-medium">
                    {edu.degree} {edu.field_of_study ? `in ${edu.field_of_study}` : ""}
                  </p>
                  <div className="flex items-center justify-between text-xs text-[#5C5C7A] pt-1">
                    {edu.graduation_year && <span>Graduation: {edu.graduation_year}</span>}
                    {edu.gpa && <span className="font-mono text-emerald-800">GPA: {edu.gpa}</span>}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Projects */}
        {projects.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FolderGit2 className="h-4 w-4 text-[#7A2D4A]" />
                Featured Projects ({projects.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {projects.map((proj, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-[#3A3A52]">{proj.name}</h4>
                    {proj.url && (
                      <a
                        href={proj.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-[#7A2D4A] hover:underline flex items-center gap-1"
                      >
                        <span>Repo</span>
                        <Globe className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {proj.description && <p className="text-xs text-[#5C5C7A] leading-relaxed">{proj.description}</p>}
                  {proj.technologies && proj.technologies.length > 0 && (
                    <div className="pt-1">
                      <SkillBadges skills={proj.technologies} maxDisplay={4} />
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Certifications */}
      {certifications.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Award className="h-4 w-4 text-[#7A2D4A]" />
              Certifications & Accreditations ({certifications.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {certifications.map((cert, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#FAF7F3] border border-[#DDD6E7] text-xs text-[#3A3A52]"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
                  <span>{typeof cert === "string" ? cert : cert.name || "Certification"}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default ResumeProfileCard
