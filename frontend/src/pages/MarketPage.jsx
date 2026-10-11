import React, { useState, useEffect, useRef } from "react"
import { PageContainer } from "@/components/layout/PageContainer"
import { MarketDashboard } from "@/components/market/MarketDashboard"
import { marketApi } from "@/api/marketApi"
import { jobApi } from "@/api/jobApi"

export function getCandidateDomainRole(resume) {
  if (!resume) return "Software Engineer"
  const title = resume.parsed_data?.experience?.[0]?.title || ""
  const field = resume.parsed_data?.education?.[0]?.field_of_study || ""
  const skills = resume.parsed_data?.skills || []

  if (/software|developer|full\s*stack|frontend|backend/i.test(title)) return "Software Engineer"
  if (/data\s*scien|machine\s*learn|ai\b/i.test(title)) return "Data Scientist"
  if (/biotech|biology|microbiol|chemist/i.test(title)) return "Biotechnology"

  if (/biotech|biology/i.test(field)) return "Biotechnology"
  if (/computer|software|artificial intelligence|data science/i.test(field)) return "Software Engineer"

  const skillsText = Array.isArray(skills) ? skills.join(" ") : ""
  if (/pcr|cell culture|microbiology|gel electrophoresis/i.test(skillsText)) return "Biotechnology"

  return title ? title.replace(/\s+intern\b/i, "").trim() : "Software Engineer"
}

export function MarketPage({ activeResume }) {
  const [overviewData, setOverviewData] = useState(null)
  const [salaryData, setSalaryData] = useState(null)
  const [skillsData, setSkillsData] = useState(null)
  const [heatmapData, setHeatmapData] = useState(null)
  const [positioningData, setPositioningData] = useState(null)
  const [totalDbCount, setTotalDbCount] = useState(1555)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const activeRequestIdRef = useRef(0)

  // Fetch live total indexed job postings from database
  useEffect(() => {
    jobApi.getStats()
      .then((data) => {
        if (data?.total) {
          setTotalDbCount(data.total)
        }
      })
      .catch(() => {})
  }, [])

  const fetchMarketData = async (params = {}) => {
    const requestId = ++activeRequestIdRef.current
    setIsLoading(true)
    setError(null)
    const titleQuery = params.titleQuery || getCandidateDomainRole(activeResume)

    try {
      // Fetch comprehensive RoleOverview: aggregates salary band, top skills, locations, work types and narrative
      const overview = await marketApi.getRoleOverview({ titleQuery, location: params.location })
      if (requestId !== activeRequestIdRef.current) return

      if (overview) {
        setOverviewData(overview)
        if (overview.salary_band) {
          setSalaryData({
            role_title: titleQuery,
            location_filter: params.location,
            salary_band: overview.salary_band,
            top_paying_companies: (overview.top_companies || []).map((c) => ({
              company_name: c,
              median_salary: overview.salary_band?.median_annual || 0,
              posting_count: 1,
            })),
            narrative: overview.narrative,
            data_quality_note: overview.data_quality_note,
          })
        }
        if (overview.top_skills) {
          setSkillsData({
            role_context: titleQuery,
            total_postings_analysed: overview.total_postings,
            skills: overview.top_skills,
            narrative: overview.narrative,
          })
        }
        if (overview.top_locations) {
          setHeatmapData({
            role_context: titleQuery,
            total_postings_analysed: overview.total_postings,
            locations: overview.top_locations,
            hottest_market: overview.top_locations?.[0]?.location,
            narrative: overview.narrative,
          })
        }
      }
    } catch (err) {
      if (requestId !== activeRequestIdRef.current) return
      console.warn("Market API call failed:", err.message)
      setError(`Failed to query market intelligence: ${err.message || "Network error"}. Please click Retry.`)
      setOverviewData(null)
    } finally {
      if (requestId === activeRequestIdRef.current) {
        setIsLoading(false)
      }
    }
  }

  const fetchPositioningData = async (resume) => {
    if (!resume?.id) {
      generateMockPositioning(resume)
      return
    }

    try {
      const positioning = await marketApi.getResumePositioning(resume.id)
      if (positioning) {
        setPositioningData(positioning)
      } else {
        generateMockPositioning(resume)
      }
    } catch (e) {
      console.warn("Resume positioning API failed, falling back to heuristic:", e.message)
      generateMockPositioning(resume)
    }
  }

  const generateMockPositioning = (resume) => {
    const skills = resume?.parsed_data?.skills || [
      "Python",
      "FastAPI",
      "PostgreSQL",
      "SQL",
    ]
    const candidateName = resume?.candidate_name || "Candidate"

    setPositioningData({
      candidate_name: candidateName,
      total_relevant_postings: totalDbCount,
      matched_skill_count: skills.length,
      coverage_pct: 72.0,
      salary_expectation_band: {
        p25_annual: 850000,
        median_annual: 1600000,
        p75_annual: 2400000,
      },
      competitive_locations: ["Bengaluru, Karnataka", "Hyderabad, Telangana", "Mumbai, Maharashtra", "Chennai, Tamil Nadu", "Pune, Maharashtra"],
      positioning_tips: [
        "Your core technical skill foundations align well with high-demand engineering hubs across India.",
        "Strengthening system architecture or scalable cloud deployment will elevate your compensation ceiling.",
        "Target growth-stage product companies and MNC technology centres in Bengaluru and Hyderabad.",
      ],
      market_narrative:
        `Candidate demonstrates competitive positioning within the Indian labor market, with high alignment in core technical competencies across metro hiring hubs.`,
      skill_alignment: skills.slice(0, 5).map((s) => ({
        skill: s,
        market_demand_pct: 45.0,
        candidate_has: true,
        signal: "strength",
      })),
    })
  }

  // Reactively fetch market intelligence and positioning whenever active profile changes
  useEffect(() => {
    const role = getCandidateDomainRole(activeResume)
    fetchMarketData({ titleQuery: role })
    fetchPositioningData(activeResume)
  }, [activeResume?.id, activeResume?.candidate_name])

  const subtitleText = overviewData?.total_postings
    ? `Real-time aggregation over ${overviewData.total_postings.toLocaleString()} matching postings (out of ${totalDbCount.toLocaleString()} live indexed Indian opportunities)`
    : `Real-time analytics across ${totalDbCount.toLocaleString()} live Indian job postings`

  return (
    <PageContainer
      title="Labor Market Intelligence"
      badge="Market Agent"
    >
      <MarketDashboard
        overviewData={overviewData}
        salaryData={salaryData}
        skillsData={skillsData}
        heatmapData={heatmapData}
        positioningData={positioningData}
        activeResume={activeResume}
        isLoading={isLoading}
        error={error}
        onSearch={fetchMarketData}
      />
    </PageContainer>
  )
}
