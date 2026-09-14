import React from "react"
import { Badge } from "@/components/ui/badge"

// Helper to determine skill color based on common categories
export function getSkillVariant(skill) {
  const s = skill.toLowerCase()
  if (s.includes("python") || s.includes("typescript") || s.includes("javascript") || s.includes("java") || s.includes("c++") || s.includes("go") || s.includes("rust")) {
    return "primary" // Blue
  }
  if (s.includes("react") || s.includes("fastapi") || s.includes("node") || s.includes("next") || s.includes("tailwind") || s.includes("vue") || s.includes("angular")) {
    return "purple" // Purple
  }
  if (s.includes("sql") || s.includes("postgres") || s.includes("mongo") || s.includes("redis") || s.includes("vector") || s.includes("neo4j")) {
    return "success" // Green
  }
  if (s.includes("aws") || s.includes("docker") || s.includes("kubernetes") || s.includes("k8s") || s.includes("ci/cd") || s.includes("cloud")) {
    return "warning" // Amber
  }
  return "default"
}

export function SkillBadges({ skills = [], maxDisplay, className = "" }) {
  if (!skills || skills.length === 0) {
    return <span className="text-xs text-slate-400 italic">No skills listed</span>
  }

  const displayedSkills = maxDisplay ? skills.slice(0, maxDisplay) : skills
  const remainingCount = maxDisplay && skills.length > maxDisplay ? skills.length - maxDisplay : 0

  return (
    <div className={`flex flex-wrap gap-1.5 items-center ${className}`}>
      {displayedSkills.map((skill, idx) => {
        const variant = getSkillVariant(skill)
        return (
          <Badge key={`${skill}-${idx}`} variant={variant}>
            {skill}
          </Badge>
        )
      })}
      {remainingCount > 0 && (
        <Badge variant="outline" className="text-slate-400">
          +{remainingCount} more
        </Badge>
      )}
    </div>
  )
}
