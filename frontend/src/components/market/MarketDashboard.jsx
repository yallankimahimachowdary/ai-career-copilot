import React, { useState, useEffect } from "react"
import {
  Search,
  MapPin,
  TrendingUp,
  DollarSign,
  PieChart,
  Compass,
  Flame,
  Loader2,
  AlertCircle,
  ShieldCheck,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { RoleOverview } from "./RoleOverview"
import { SalaryChart } from "./SalaryChart"
import { TrendingSkills } from "./TrendingSkills"
import { DemandHeatmap } from "./DemandHeatmap"
import { ResumePositioning } from "./ResumePositioning"
import { JobFreshnessTracker } from "./JobFreshnessTracker"
import { getCandidateDomainRole } from "@/pages/MarketPage"

export function MarketDashboard({
  overviewData,
  salaryData,
  skillsData,
  heatmapData,
  positioningData,
  activeResume,
  isLoading,
  error,
  onSearch,
}) {
  const [activeTab, setActiveTab] = useState("overview")
  const [roleQuery, setRoleQuery] = useState(() => getCandidateDomainRole(activeResume))
  const [locationQuery, setLocationQuery] = useState("")

  useEffect(() => {
    const role = getCandidateDomainRole(activeResume)
    setRoleQuery(role)
  }, [activeResume?.id, activeResume?.candidate_name])

  const handleRunSearch = (e) => {
    e?.preventDefault()
    if (onSearch) {
      onSearch({
        titleQuery: roleQuery.trim() || "Software Engineer",
        location: locationQuery.trim() || undefined,
      })
    }
  }

  return (
    <div className="space-y-6">
      {/* Search Header Bar */}
      <Card className="border-[#DDD6E7] bg-white shadow-sm">
        <CardContent className="p-5">
          <form onSubmit={handleRunSearch} className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="h-4 w-4 absolute left-3 top-3 text-[#5C5C7A]" />
              <Input
                placeholder="Target Job Title (e.g. Senior Backend Engineer, Data Scientist)..."
                value={roleQuery}
                onChange={(e) => setRoleQuery(e.target.value)}
                className="pl-9 bg-white border-[#DDD6E7] text-[#3A3A52] focus:border-[#7A2D4A]"
              />
            </div>

            <div className="relative w-full sm:w-64">
              <MapPin className="h-4 w-4 absolute left-3 top-3 text-[#5C5C7A]" />
              <Input
                placeholder="Location filter (optional)..."
                value={locationQuery}
                onChange={(e) => setLocationQuery(e.target.value)}
                className="pl-9 bg-white border-[#DDD6E7] text-[#3A3A52] focus:border-[#7A2D4A]"
              />
            </div>

            <Button type="submit" variant="default" disabled={isLoading} className="shrink-0 w-full sm:w-auto bg-[#7A2D4A] hover:bg-[#63233B] text-white">
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Querying Labor Dataset...</span>
                </>
              ) : (
                <>
                  <TrendingUp className="h-4 w-4 mr-2" />
                  <span>Analyze Market Dynamics</span>
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <div>
              <span className="font-semibold">Market Intelligence Agent Error: </span>
              <span>{error}</span>
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
            onClick={handleRunSearch}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Sub-tabs Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 w-full">
          <TabsTrigger value="overview" className="text-xs">
            <PieChart className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Role Overview
          </TabsTrigger>
          <TabsTrigger value="salary" className="text-xs">
            <DollarSign className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Salary Spectrum
          </TabsTrigger>
          <TabsTrigger value="skills" className="text-xs">
            <Flame className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Skill Demand
          </TabsTrigger>
          <TabsTrigger value="heatmap" className="text-xs">
            <MapPin className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Geography
          </TabsTrigger>
          <TabsTrigger value="positioning" className="text-xs">
            <Compass className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            My Positioning
          </TabsTrigger>
          <TabsTrigger value="freshness" className="text-xs">
            <ShieldCheck className="h-3.5 w-3.5 mr-1.5 text-[#7A2D4A]" />
            Data Freshness
          </TabsTrigger>
        </TabsList>

        {isLoading && (
          <div className="pt-4 space-y-4">
            <div className="p-4 rounded-xl border border-[#DDD6E7] bg-[#EDE7F6]/60 flex items-center gap-3">
              <Loader2 className="h-5 w-5 text-[#7A2D4A] animate-spin shrink-0" />
              <div>
                <p className="text-xs font-semibold text-[#3A3A52]">Querying Labor Market Dataset</p>
                <p className="text-[11px] text-[#5C5C7A]">
                  Aggregating compensation percentiles, skill occurrences, and geographic distribution...
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-28 rounded-xl border border-[#DDD6E7] bg-white p-5 animate-pulse space-y-3">
                  <div className="h-3 bg-[#EDE7F6] rounded w-2/3" />
                  <div className="h-7 bg-[#FAF7F3] rounded w-1/2" />
                  <div className="h-2.5 bg-[#EDE7F6] rounded w-3/4" />
                </div>
              ))}
            </div>
            <div className="h-64 rounded-xl border border-[#DDD6E7] bg-white p-6 animate-pulse space-y-4">
              <div className="h-4 bg-[#EDE7F6] rounded w-1/4" />
              <div className="h-44 bg-[#FAF7F3] rounded" />
            </div>
          </div>
        )}

        {!isLoading && (
          <TabsContent value="overview" className="pt-2">
            <RoleOverview overview={overviewData} />
          </TabsContent>
        )}

        {!isLoading && (
          <TabsContent value="salary" className="pt-2">
            <SalaryChart
              salaryBand={salaryData?.salary_band || overviewData?.salary_band}
              topPayingCompanies={salaryData?.top_paying_companies || []}
              narrative={salaryData?.narrative || overviewData?.narrative}
            />
          </TabsContent>
        )}

        {!isLoading && (
          <TabsContent value="skills" className="pt-2">
            <TrendingSkills
              skills={skillsData?.skills || overviewData?.top_skills}
              totalPostings={skillsData?.total_postings_analysed || overviewData?.total_postings}
              narrative={skillsData?.narrative || overviewData?.narrative}
            />
          </TabsContent>
        )}

        {!isLoading && (
          <TabsContent value="heatmap" className="pt-2">
            <DemandHeatmap
              locations={heatmapData?.locations || overviewData?.top_locations}
              hottestMarket={heatmapData?.hottest_market || overviewData?.top_locations?.[0]?.location}
              narrative={heatmapData?.narrative || overviewData?.narrative}
            />
          </TabsContent>
        )}

        {!isLoading && (
          <TabsContent value="positioning" className="pt-2">
            <ResumePositioning positioning={positioningData} />
          </TabsContent>
        )}

        <TabsContent value="freshness" className="pt-2">
          <JobFreshnessTracker />
        </TabsContent>
      </Tabs>
    </div>
  )
}
