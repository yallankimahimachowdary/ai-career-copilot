import React, { useState, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { PageContainer } from "@/components/layout/PageContainer"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { jobApi } from "@/api/jobApi"
import { matchApi } from "@/api/matchApi"
import {
  FileText,
  Briefcase,
  GraduationCap,
  TrendingUp,
  Sparkles,
  ArrowRight,
  UploadCloud,
  Building,
  MapPin,
  ShieldCheck,
} from "lucide-react"

export function DashboardPage({ activeResume, onSelectDemoResume, onSelectJobForCoach }) {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [jobStats, setJobStats] = useState({ total: 0 })
  const [topMatches, setTopMatches] = useState([])
  const [isLoadingMatches, setIsLoadingMatches] = useState(false)
  const [refreshStatus, setRefreshStatus] = useState(null)

  const studentName =
    user?.full_name ||
    activeResume?.candidate_name ||
    user?.email?.split("@")[0] ||
    "Student"

  // Fetch job counts and refresh status on mount
  useEffect(() => {
    let isMounted = true

    const loadPlatformOverview = async () => {
      try {
        const stats = await jobApi.getStats().catch(() => ({ total: 0 }))
        if (isMounted) setJobStats(stats)
      } catch {
        // ignore
      }

      try {
        const statusData = await jobApi.getRefreshStatus().catch(() => null)
        if (isMounted && statusData) setRefreshStatus(statusData)
      } catch {
        // ignore
      }
    }

    loadPlatformOverview()
    return () => {
      isMounted = false
    }
  }, [])

  // Fetch top 3 matches for the active resume
  useEffect(() => {
    let isMounted = true
    if (!activeResume?.id) {
      setTopMatches([])
      return
    }

    const loadTopMatches = async () => {
      setIsLoadingMatches(true)
      try {
        const response = await matchApi.matchJobsForResume(activeResume.id, { limit: 3 })
        const matchesList = response?.matches || []
        if (isMounted) setTopMatches(matchesList.slice(0, 3))
      } catch {
        if (isMounted) setTopMatches([])
      } finally {
        if (isMounted) setIsLoadingMatches(false)
      }
    }

    loadTopMatches()
    return () => {
      isMounted = false
    }
  }, [activeResume?.id])

  const skillsCount =
    activeResume?.skills_count ||
    activeResume?.parsed_data?.skills?.length ||
    0

  const highestScore =
    topMatches.length > 0
      ? Math.round((topMatches[0].final_score || topMatches[0].composite_score || 0) * 100)
      : null

  return (
    <PageContainer
      title="Student Career Command Center"
      badge="Multi-Agent Pipeline"
    >
      <div className="space-y-8">
        {/* Welcome & Overview Banner */}
        <div className="rounded-2xl border border-[#DDD6E7] bg-white p-6 sm:p-8 shadow-xs relative overflow-hidden">
          <div className="absolute right-0 top-0 h-full w-1/3 bg-linear-to-l from-[#EDE7F6]/60 to-transparent pointer-events-none hidden md:block" />
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#7A2D4A]">
                <Sparkles className="h-4 w-4" />
                <span>Personalized Career Co-Pilot</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#3A3A52]">
                Welcome back, {studentName}
              </h1>
              <p className="text-sm text-[#5C5C7A] max-w-2xl leading-relaxed">
                Your explainable multi-agent copilot evaluates technical job readiness, extracts profile entities,
                and simulates practice interviews using real-time market data.
              </p>
            </div>

            <div className="flex flex-wrap sm:flex-nowrap gap-3 shrink-0">
              <Button
                onClick={() => navigate("/resume")}
                className="bg-[#7A2D4A] hover:bg-[#63233B] text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xs"
              >
                <UploadCloud className="h-4 w-4 mr-2" />
                Upload New Resume
              </Button>
              {!activeResume && onSelectDemoResume && (
                <Button
                  variant="secondary"
                  onClick={onSelectDemoResume}
                  className="border border-[#DDD6E7] bg-[#EDE7F6] text-[#7A2D4A] hover:bg-[#DDD6E7] text-xs font-semibold px-4 py-2.5 rounded-xl"
                >
                  <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                  Explore Demo Profile
                </Button>
              )}
            </div>
          </div>

          {/* Quick Metrics Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-[#E5E3EB]">
            <div className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#5C5C7A]">Active Resume</span>
              <div className="font-bold text-sm sm:text-base text-[#3A3A52] truncate">
                {activeResume?.candidate_name || activeResume?.filename || "None Loaded"}
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#5C5C7A]">Identified Skills</span>
              <div className="font-bold text-sm sm:text-base text-[#7A2D4A] font-mono">
                {skillsCount > 0 ? `${skillsCount} skills` : "—"}
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#5C5C7A]">Top Match Fit</span>
              <div className="font-bold text-sm sm:text-base text-emerald-800 font-mono">
                {highestScore !== null ? `${highestScore}%` : "—"}
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#5C5C7A]">Indexed Market Jobs</span>
              <div className="font-bold text-sm sm:text-base text-[#3A3A52] font-mono">
                {jobStats.total > 0 ? `${jobStats.total.toLocaleString()} postings` : "Indexing..."}
              </div>
            </div>
          </div>
        </div>

        {/* 4 Agent Pipeline Workflows */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-[#3A3A52] tracking-tight">Core Career Pipelines</h2>
            <span className="text-xs text-[#5C5C7A]">Direct access to specialized intelligent agents</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* Pipeline 1: Resume */}
            <Card className="hover:border-[#7A2D4A]/50 transition-all duration-200 group flex flex-col justify-between border-[#DDD6E7]">
              <CardContent className="p-5 space-y-4 flex flex-col justify-between h-full">
                <div className="space-y-3">
                  <div className="h-10 w-10 rounded-xl bg-[#EDE7F6] text-[#7A2D4A] flex items-center justify-center group-hover:bg-[#7A2D4A] group-hover:text-white transition-colors">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-medium text-[#7A2D4A] bg-[#EDE7F6] px-2 py-0.5 rounded">
                      Parser Agent
                    </span>
                    <h3 className="text-base font-bold text-[#3A3A52] mt-1.5 group-hover:text-[#7A2D4A] transition-colors">
                      Resume & Profile
                    </h3>
                  </div>
                  <p className="text-xs text-[#5C5C7A] leading-relaxed">
                    Extracts structured entities, verifies skills against canonical patterns, and calculates dense embeddings.
                  </p>
                </div>
                <Link
                  to="/resume"
                  className="inline-flex items-center text-xs font-semibold text-[#7A2D4A] hover:underline pt-2"
                >
                  <span>Manage Profile</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                </Link>
              </CardContent>
            </Card>

            {/* Pipeline 2: Matches */}
            <Card className="hover:border-[#7A2D4A]/50 transition-all duration-200 group flex flex-col justify-between border-[#DDD6E7]">
              <CardContent className="p-5 space-y-4 flex flex-col justify-between h-full">
                <div className="space-y-3">
                  <div className="h-10 w-10 rounded-xl bg-[#EDE7F6] text-[#7A2D4A] flex items-center justify-center group-hover:bg-[#7A2D4A] group-hover:text-white transition-colors">
                    <Briefcase className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-medium text-[#7A2D4A] bg-[#EDE7F6] px-2 py-0.5 rounded">
                      Matcher Agent
                    </span>
                    <h3 className="text-base font-bold text-[#3A3A52] mt-1.5 group-hover:text-[#7A2D4A] transition-colors">
                      Job Matches & XAI
                    </h3>
                  </div>
                  <p className="text-xs text-[#5C5C7A] leading-relaxed">
                    Calculates composite weighted scores and explains ranking decisions with SHAP feature attributions.
                  </p>
                </div>
                <Link
                  to="/matches"
                  className="inline-flex items-center text-xs font-semibold text-[#7A2D4A] hover:underline pt-2"
                >
                  <span>Explore Matches</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                </Link>
              </CardContent>
            </Card>

            {/* Pipeline 3: Coach */}
            <Card className="hover:border-[#7A2D4A]/50 transition-all duration-200 group flex flex-col justify-between border-[#DDD6E7]">
              <CardContent className="p-5 space-y-4 flex flex-col justify-between h-full">
                <div className="space-y-3">
                  <div className="h-10 w-10 rounded-xl bg-[#EDE7F6] text-[#7A2D4A] flex items-center justify-center group-hover:bg-[#7A2D4A] group-hover:text-white transition-colors">
                    <GraduationCap className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-medium text-[#7A2D4A] bg-[#EDE7F6] px-2 py-0.5 rounded">
                      Coach Agent
                    </span>
                    <h3 className="text-base font-bold text-[#3A3A52] mt-1.5 group-hover:text-[#7A2D4A] transition-colors">
                      Interview Coach
                    </h3>
                  </div>
                  <p className="text-xs text-[#5C5C7A] leading-relaxed">
                    Pinpoints critical skill gaps, builds curated question banks, and scores practice answers with rubrics.
                  </p>
                </div>
                <Link
                  to="/coach"
                  className="inline-flex items-center text-xs font-semibold text-[#7A2D4A] hover:underline pt-2"
                >
                  <span>Start Practice</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                </Link>
              </CardContent>
            </Card>

            {/* Pipeline 4: Market */}
            <Card className="hover:border-[#7A2D4A]/50 transition-all duration-200 group flex flex-col justify-between border-[#DDD6E7]">
              <CardContent className="p-5 space-y-4 flex flex-col justify-between h-full">
                <div className="space-y-3">
                  <div className="h-10 w-10 rounded-xl bg-[#EDE7F6] text-[#7A2D4A] flex items-center justify-center group-hover:bg-[#7A2D4A] group-hover:text-white transition-colors">
                    <TrendingUp className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-medium text-[#7A2D4A] bg-[#EDE7F6] px-2 py-0.5 rounded">
                      Market Agent
                    </span>
                    <h3 className="text-base font-bold text-[#3A3A52] mt-1.5 group-hover:text-[#7A2D4A] transition-colors">
                      Market & Freshness
                    </h3>
                  </div>
                  <p className="text-xs text-[#5C5C7A] leading-relaxed">
                    Surveys salary percentiles, tracks trending technology stacks, and monitors ingestion freshness.
                  </p>
                </div>
                <Link
                  to="/market"
                  className="inline-flex items-center text-xs font-semibold text-[#7A2D4A] hover:underline pt-2"
                >
                  <span>View Trends</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Two-Column Section: Top Matches Preview + Ingestion Health */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Top Matches Preview (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-[#3A3A52] flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-[#7A2D4A]" />
                Top Recommended Matches
              </h2>
              {topMatches.length > 0 && (
                <Link to="/matches" className="text-xs text-[#7A2D4A] font-semibold hover:underline">
                  View all ({topMatches.length})
                </Link>
              )}
            </div>

            {isLoadingMatches ? (
              <div className="p-8 border border-[#DDD6E7] rounded-2xl bg-white text-center text-xs text-[#5C5C7A]">
                Evaluating profile match vectors...
              </div>
            ) : topMatches.length > 0 ? (
              <div className="space-y-3">
                {topMatches.map((m, idx) => {
                  const score = Math.round((m.final_score || m.composite_score || 0) * 100)
                  return (
                    <div
                      key={idx}
                      className="rounded-xl border border-[#DDD6E7] bg-white p-4 shadow-xs flex items-center justify-between gap-4 hover:border-[#7A2D4A]/40 transition-colors"
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-[#5C5C7A]">#{idx + 1}</span>
                          <h4 className="font-bold text-sm text-[#3A3A52] truncate">{m.title}</h4>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-[#5C5C7A]">
                          <span className="flex items-center gap-1 truncate">
                            <Building className="h-3 w-3" />
                            {m.company_name || "Not specified"}
                          </span>
                          <span className="flex items-center gap-1 truncate">
                            <MapPin className="h-3 w-3" />
                            {m.location || "Location not specified"}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-right">
                          <div className="text-base font-bold text-[#7A2D4A] font-mono">{score}%</div>
                          <span className="text-[10px] text-[#5C5C7A]">Fit Score</span>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            if (onSelectJobForCoach) onSelectJobForCoach(m)
                            navigate(`/coach?job_id=${m.job_id}`)
                          }}
                          className="text-xs hover:bg-[#7A2D4A] hover:text-white hover:border-[#7A2D4A]"
                        >
                          Coach Gap
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-[#DDD6E7] bg-white p-8 text-center space-y-3">
                <FileText className="h-8 w-8 text-[#7A2D4A] mx-auto opacity-80" />
                <h4 className="text-sm font-semibold text-[#3A3A52]">No Matches Computed Yet</h4>
                <p className="text-xs text-[#5C5C7A] max-w-sm mx-auto">
                  Upload your resume or activate the demo profile to view ranked job postings with SHAP explainability.
                </p>
                <div className="pt-2">
                  <Button
                    size="sm"
                    onClick={() => navigate("/resume")}
                    className="bg-[#7A2D4A] hover:bg-[#63233B] text-white text-xs font-semibold"
                  >
                    Go to Resume Ingestion
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Ingestion & Integrity Panel (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <h2 className="text-base font-bold text-[#3A3A52] flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#7A2D4A]" />
              Data Freshness & Integrity
            </h2>

            <Card className="border-[#DDD6E7] bg-white shadow-xs">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#E5E3EB]">
                  <span className="text-xs text-[#5C5C7A]">Ingestion Service</span>
                  <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">
                    Operational
                  </Badge>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[#5C5C7A]">Frozen Ranking Weights:</span>
                    <span className="font-mono font-medium text-[#3A3A52]">BM25 0.10 | SBERT 0.10 | Overlap 0.80</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#5C5C7A]">Ingestion Sources:</span>
                    <span className="font-medium text-[#3A3A52]">Adzuna API + Kaggle Snapshot</span>
                  </div>
                  {refreshStatus?.last_run && (
                    <div className="flex justify-between">
                      <span className="text-[#5C5C7A]">Last Ingestion Cycle:</span>
                      <span className="font-mono text-[#3A3A52]">
                        {new Date(refreshStatus.last_run.finished_at || refreshStatus.last_run.started_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="rounded-xl bg-[#FAF7F3] p-3 text-[11px] text-[#5C5C7A] border border-[#DDD6E7] leading-relaxed">
                  <strong>Scientific Notice:</strong> Rankings and skill recommendations reflect algorithmic similarity
                  and statistical market signals. They do not guarantee employment or interview offers.
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}

export default DashboardPage
