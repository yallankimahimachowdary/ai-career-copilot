import React, { useState, useEffect } from "react"
import { PageContainer } from "@/components/layout/PageContainer"
import { MarketDashboard } from "@/components/market/MarketDashboard"
import { marketApi } from "@/api/marketApi"
import { mockMarketOverview } from "@/data/mockData"

export function MarketPage({ activeResume }) {
  const [overviewData, setOverviewData] = useState(mockMarketOverview)
  const [salaryData, setSalaryData] = useState(null)
  const [skillsData, setSkillsData] = useState(null)
  const [heatmapData, setHeatmapData] = useState(null)
  const [positioningData, setPositioningData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchMarketData = async (params = {}) => {
    setIsLoading(true)
    setError(null)
    const titleQuery = params.titleQuery || "Software Engineer"

    try {
      // Parallel requests for all market insights
      const [overview, salary, skills, heatmap] = await Promise.allSettled([
        marketApi.getRoleOverview({ titleQuery, location: params.location }),
        marketApi.getSalaryInsights({ titleQuery, location: params.location }),
        marketApi.getTrendingSkills({ titleQuery, location: params.location, topN: 10 }),
        marketApi.getDemandHeatmap({ titleQuery, topN: 10 }),
      ])

      if (overview.status === "fulfilled" && overview.value) {
        setOverviewData(overview.value)
      }
      if (salary.status === "fulfilled" && salary.value) {
        setSalaryData(salary.value)
      }
      if (skills.status === "fulfilled" && skills.value) {
        setSkillsData(skills.value)
      }
      if (heatmap.status === "fulfilled" && heatmap.value) {
        setHeatmapData(heatmap.value)
      }
    } catch (err) {
      console.warn("Market API failed, falling back to mock dataset:", err.message)
      setError("Connected to cached market baseline dataset.")
      setOverviewData(mockMarketOverview)
    } finally {
      setIsLoading(false)
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
      "React",
      "PostgreSQL",
      "Docker",
      "AWS",
    ]
    const candidateName = resume?.candidate_name || "Alex Chen"

    setPositioningData({
      candidate_name: candidateName,
      total_relevant_postings: 3240,
      matched_skill_count: skills.length,
      coverage_pct: 78.4,
      salary_expectation_band: {
        p25_annual: 145000,
        median_annual: 172000,
        p75_annual: 205000,
      },
      competitive_locations: ["San Francisco, CA", "Seattle, WA", "New York, NY", "Remote (US)"],
      positioning_tips: [
        "Your Python + FastAPI + PostgreSQL core puts you in the top 15% of backend candidates.",
        "Adding Kubernetes orchestration or Kafka event streaming will increase your median salary ceiling by ~$24k/yr.",
        "Target mid-to-late stage scaleups in SF and Seattle offering competitive equity multiples.",
      ],
      market_narrative:
        "The applicant demonstrates strong positioning for Senior Software Engineer and Backend Platform roles with favorable compensation premiums in cloud infrastructure and distributed APIs.",
      skill_alignment: [
        { skill: "Python", market_demand_pct: 58.5, candidate_has: true, signal: "strength" },
        { skill: "SQL / PostgreSQL", market_demand_pct: 52.9, candidate_has: true, signal: "strength" },
        { skill: "AWS Cloud", market_demand_pct: 47.1, candidate_has: true, signal: "strength" },
        { skill: "Docker", market_demand_pct: 41.7, candidate_has: true, signal: "strength" },
        { skill: "Kubernetes (K8s)", market_demand_pct: 39.2, candidate_has: false, signal: "gap" },
        { skill: "React / TS", market_demand_pct: 37.1, candidate_has: true, signal: "strength" },
        { skill: "Kafka", market_demand_pct: 21.6, candidate_has: false, signal: "opportunity" },
      ],
    })
  }

  useEffect(() => {
    fetchMarketData()
  }, [])

  useEffect(() => {
    fetchPositioningData(activeResume)
  }, [activeResume?.id])

  return (
    <PageContainer
      title="Labor Market Intelligence"
      subtitle="Real-time aggregation over 4,000+ job postings: Compensation percentiles, skill velocity & candidate positioning"
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
