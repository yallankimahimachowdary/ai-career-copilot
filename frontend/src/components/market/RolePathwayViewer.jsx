import React, { useState, useEffect } from "react"
import { GitFork, ArrowRight, Clock, Award, AlertCircle, Loader2, Sparkles, RefreshCw } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { graphApi } from "@/api/graphApi"

export function RolePathwayViewer({ activeResume, defaultRole = "Software Engineer" }) {
  const [roleInput, setRoleInput] = useState(defaultRole)
  const [pathwayData, setPathwayData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const candidateSkills = activeResume?.parsed_data?.skills || []

  const fetchPathway = async (targetRole) => {
    const role = (targetRole || roleInput).trim()
    if (!role) return

    setIsLoading(true)
    setError(null)
    try {
      const data = await graphApi.getRolePathway(role, candidateSkills)
      setPathwayData(data)
    } catch (err) {
      console.warn("Role pathway fetch failed:", err.message)
      setError(err.message || "Failed to load role progression pathways.")
      setPathwayData(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (defaultRole) {
      setRoleInput(defaultRole)
      fetchPathway(defaultRole)
    }
  }, [defaultRole])

  const handleSubmit = (e) => {
    e.preventDefault()
    fetchPathway(roleInput)
  }

  return (
    <div className="space-y-6">
      {/* Search & Control Card */}
      <Card className="border-[#DDD6E7] bg-white shadow-sm">
        <CardContent className="p-5">
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <GitFork className="h-4 w-4 absolute left-3 top-3 text-[#5C5C7A]" />
              <Input
                placeholder="Enter starting role (e.g. Junior Web Developer Trainee, Software Engineer)..."
                value={roleInput}
                onChange={(e) => setRoleInput(e.target.value)}
                className="pl-9 bg-white border-[#DDD6E7] text-[#3A3A52] focus:border-[#7A2D4A]"
              />
            </div>
            <Button
              type="submit"
              disabled={isLoading || !roleInput.trim()}
              className="shrink-0 bg-[#7A2D4A] hover:bg-[#63233B] text-white w-full sm:w-auto"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Traversing Graph...</span>
                </>
              ) : (
                <>
                  <GitFork className="h-4 w-4 mr-2" />
                  <span>Explore Career Pathways</span>
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <div>
              <span className="font-semibold">Knowledge Graph Query Error: </span>
              <span>{error}</span>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
            onClick={() => fetchPathway(roleInput)}
          >
            <RefreshCw className="h-3 w-3 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="p-8 rounded-xl border border-[#DDD6E7] bg-white space-y-4 animate-pulse">
          <div className="h-4 bg-[#EDE7F6] rounded w-1/3" />
          <div className="h-20 bg-[#FAF7F3] rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="h-32 bg-[#FAF7F3] rounded" />
            <div className="h-32 bg-[#FAF7F3] rounded" />
          </div>
        </div>
      )}

      {/* Results */}
      {!isLoading && pathwayData && (
        <div className="space-y-6">
          {/* Summary Card */}
          <Card className="border-[#DDD6E7] bg-[#EDE7F6]">
            <CardContent className="p-5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-[#7A2D4A] uppercase tracking-wider">
                  Progression Graph Hierarchy
                </span>
                <Badge variant="outline" className="bg-white text-[#7A2D4A] border-[#DDD6E7]">
                  {pathwayData.total_reachable_roles} Reachable Roles Found
                </Badge>
              </div>
              <h3 className="text-lg font-bold text-[#3A3A52]">
                Career Trajectories from &quot;{pathwayData.starting_role}&quot;
              </h3>
              {pathwayData.summary && (
                <p className="text-xs text-[#5C5C7A] leading-relaxed pt-1">
                  {pathwayData.summary}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Pathways List */}
          {pathwayData.pathways && pathwayData.pathways.length > 0 ? (
            <div className="grid grid-cols-1 gap-4">
              {pathwayData.pathways.map((path, idx) => (
                <Card key={idx} className="border-[#DDD6E7] bg-white shadow-xs hover:border-[#7A2D4A]/50 transition-all">
                  <CardHeader className="pb-3 border-b border-[#DDD6E7]">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="p-1 rounded-md bg-[#EDE7F6] text-[#7A2D4A]">
                          <Award className="h-4 w-4" />
                        </span>
                        <div>
                          <CardTitle className="text-base text-[#3A3A52]">{path.target_role}</CardTitle>
                          <span className="text-[11px] text-[#5C5C7A]">
                            Family: <strong className="text-[#3A3A52]">{path.target_family}</strong> • Level: <strong className="text-[#3A3A52]">{path.target_level}</strong>
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 self-start sm:self-auto">
                        <span className="flex items-center gap-1 text-xs text-[#5C5C7A] font-mono bg-[#FAF7F3] px-2.5 py-1 rounded-md border border-[#DDD6E7]">
                          <Clock className="h-3 w-3 text-[#7A2D4A]" />
                          ~{path.total_years} yrs
                        </span>
                        <Badge variant="primary" className="text-[10px]">
                          Depth {path.depth}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    {/* Path Chain */}
                    {path.role_path && path.role_path.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[11px] font-semibold text-[#5C5C7A] block">Progression Step Sequence:</span>
                        <div className="flex flex-wrap items-center gap-1.5 text-xs font-medium">
                          {path.role_path.map((roleNode, rIdx) => (
                            <React.Fragment key={rIdx}>
                              <span className={`px-2.5 py-1 rounded-md border ${
                                rIdx === path.role_path.length - 1
                                  ? "bg-[#7A2D4A] text-white border-[#7A2D4A] font-bold"
                                  : rIdx === 0
                                  ? "bg-[#EDE7F6] text-[#3A3A52] border-[#DDD6E7]"
                                  : "bg-[#FAF7F3] text-[#3A3A52] border-[#DDD6E7]"
                              }`}>
                                {roleNode}
                              </span>
                              {rIdx < path.role_path.length - 1 && (
                                <ArrowRight className="h-3.5 w-3.5 text-[#5C5C7A] shrink-0" />
                              )}
                            </React.Fragment>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Transition Types */}
                    {path.transition_types && path.transition_types.length > 0 && (
                      <div className="flex items-center gap-1.5 text-xs text-[#5C5C7A]">
                        <span className="text-[11px] font-semibold">Transition:</span>
                        {path.transition_types.map((tt, tIdx) => (
                          <span key={tIdx} className="capitalize text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                            {tt.toLowerCase().replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Skills Grid: Required vs Missing */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                      {path.required_skills && path.required_skills.length > 0 && (
                        <div className="p-3 rounded-lg bg-[#FAF7F3] border border-[#DDD6E7] space-y-1.5">
                          <span className="text-[11px] font-semibold text-[#3A3A52] block">Required Skills:</span>
                          <div className="flex flex-wrap gap-1">
                            {path.required_skills.map((sk, sIdx) => (
                              <span key={sIdx} className="text-[10px] px-2 py-0.5 rounded bg-white text-[#3A3A52] border border-[#DDD6E7]">
                                {sk}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {path.missing_skills && path.missing_skills.length > 0 ? (
                        <div className="p-3 rounded-lg bg-red-50 border border-red-200 space-y-1.5">
                          <span className="text-[11px] font-semibold text-red-800 block">Bridge Skills Needed:</span>
                          <div className="flex flex-wrap gap-1">
                            {path.missing_skills.map((sk, sIdx) => (
                              <span key={sIdx} className="text-[10px] px-2 py-0.5 rounded bg-white text-red-700 border border-red-300 font-medium">
                                {sk}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-emerald-600 shrink-0" />
                          <span className="text-xs text-emerald-800 font-medium">All prerequisite skills matched!</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center rounded-2xl border border-[#DDD6E7] bg-white space-y-2">
              <GitFork className="h-8 w-8 text-[#5C5C7A] mx-auto opacity-50" />
              <p className="text-sm font-semibold text-[#3A3A52]">No progression pathways found from this role.</p>
              <p className="text-xs text-[#5C5C7A]">
                Try searching for a foundational role (e.g. &quot;Junior Web Developer Trainee&quot; or &quot;Software Engineer&quot;).
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default RolePathwayViewer
