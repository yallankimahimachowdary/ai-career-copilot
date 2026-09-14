import React from "react"
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
} from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { SkillBadges } from "./SkillBadges"
import { Badge } from "@/components/ui/badge"

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

export function ResumeProfileCard({ resume }) {
  if (!resume || !resume.parsed_data) {
    return (
      <div className="flex flex-col items-center justify-center p-12 border border-slate-800 rounded-2xl bg-slate-900/30 text-center space-y-3">
        <Sparkles className="h-10 w-10 text-slate-600 animate-pulse" />
        <p className="text-sm text-slate-400">Select or upload a resume to view extracted profile entities.</p>
      </div>
    )
  }

  const { parsed_data } = resume
  const contact = parsed_data.contact_info || {}
  const skills = parsed_data.skills || []
  const experience = parsed_data.experience || []
  const education = parsed_data.education || []
  const projects = parsed_data.projects || []
  const certifications = parsed_data.certifications || []

  return (
    <div className="space-y-6">
      {/* Top Profile Summary Header Card */}
      <Card className="border-blue-500/30 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950/20">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  {contact.name || resume.candidate_name || "Candidate Profile"}
                </h2>
                <Badge variant="primary" className="font-mono text-[11px]">
                  Parsed by Agent
                </Badge>
              </div>

              {/* Contact Chips */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-300 pt-1">
                {contact.email && (
                  <a
                    href={`mailto:${contact.email}`}
                    className="flex items-center gap-1.5 hover:text-blue-400 transition-colors"
                  >
                    <Mail className="h-3.5 w-3.5 text-blue-400" />
                    <span>{contact.email}</span>
                  </a>
                )}
                {contact.phone && (
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Phone className="h-3.5 w-3.5 text-slate-500" />
                    <span>{contact.phone}</span>
                  </span>
                )}
                {contact.location && (
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <MapPin className="h-3.5 w-3.5 text-slate-500" />
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
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs text-slate-300 hover:text-white transition-colors border border-slate-700"
                  >
                    <LinkedinIcon className="h-3.5 w-3.5 text-blue-400" />
                    <span>LinkedIn</span>
                  </a>
                )}
                {contact.github_url && (
                  <a
                    href={contact.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs text-slate-300 hover:text-white transition-colors border border-slate-700"
                  >
                    <GithubIcon className="h-3.5 w-3.5 text-slate-400" />
                    <span>GitHub</span>
                  </a>
                )}
                {contact.portfolio_url && (
                  <a
                    href={contact.portfolio_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs text-slate-300 hover:text-white transition-colors border border-slate-700"
                  >
                    <Globe className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Portfolio</span>
                  </a>
                )}
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="flex sm:flex-col gap-2 shrink-0">
              <div className="rounded-xl bg-slate-800/80 p-3 border border-slate-700/80 text-center min-w-[110px]">
                <div className="text-xl font-bold text-blue-400">{skills.length}</div>
                <div className="text-[11px] text-slate-400 uppercase tracking-wider">Identified Skills</div>
              </div>
              <div className="rounded-xl bg-slate-800/80 p-3 border border-slate-700/80 text-center min-w-[110px]">
                <div className="text-xl font-bold text-emerald-400">{experience.length}</div>
                <div className="text-[11px] text-slate-400 uppercase tracking-wider">Experience Roles</div>
              </div>
            </div>
          </div>

          {/* Professional Summary */}
          {parsed_data.summary && (
            <div className="mt-5 pt-4 border-t border-slate-800/80">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                Professional Summary
              </h4>
              <p className="text-sm text-slate-300 leading-relaxed">{parsed_data.summary}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Skills Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-400" />
              Extracted Technical Skills & Tools ({skills.length})
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <SkillBadges skills={skills} />
        </CardContent>
      </Card>

      {/* Experience Timeline */}
      {experience.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-indigo-400" />
              Work Experience ({experience.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {experience.map((exp, idx) => (
              <div key={idx} className="relative pl-6 border-l-2 border-slate-800 space-y-2">
                <div className="absolute -left-[9px] top-1 h-4 w-4 rounded-full bg-slate-900 border-2 border-indigo-500" />
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div>
                    <h4 className="text-base font-semibold text-white">{exp.title}</h4>
                    <p className="text-sm text-indigo-400 font-medium">{exp.company}</p>
                  </div>
                  <div className="text-xs text-slate-400 font-mono">
                    {exp.start_date || "N/A"} — {exp.is_current ? "Present" : exp.end_date || "N/A"}
                    {exp.location && ` • ${exp.location}`}
                  </div>
                </div>

                {exp.description && exp.description.length > 0 && (
                  <ul className="space-y-1.5 pt-1 text-sm text-slate-300 list-disc list-outside pl-4">
                    {exp.description.map((bullet, bIdx) => (
                      <li key={bIdx} className="leading-relaxed">
                        {bullet}
                      </li>
                    ))}
                  </ul>
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
                <GraduationCap className="h-4 w-4 text-emerald-400" />
                Education ({education.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {education.map((edu, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800/80 space-y-1">
                  <h4 className="text-sm font-semibold text-white">{edu.institution}</h4>
                  <p className="text-xs text-slate-300 font-medium">
                    {edu.degree} {edu.field_of_study ? `in ${edu.field_of_study}` : ""}
                  </p>
                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                    {edu.graduation_year && <span>Graduation: {edu.graduation_year}</span>}
                    {edu.gpa && <span className="font-mono text-emerald-400">GPA: {edu.gpa}</span>}
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
                <FolderGit2 className="h-4 w-4 text-cyan-400" />
                Featured Projects ({projects.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {projects.map((proj, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-white">{proj.name}</h4>
                    {proj.url && (
                      <a
                        href={proj.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
                      >
                        <span>Repo</span>
                        <Globe className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {proj.description && <p className="text-xs text-slate-300 leading-relaxed">{proj.description}</p>}
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
              <Award className="h-4 w-4 text-amber-400" />
              Certifications & Accreditations ({certifications.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {certifications.map((cert, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-amber-500/20 text-xs text-amber-200"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-amber-400 shrink-0" />
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
