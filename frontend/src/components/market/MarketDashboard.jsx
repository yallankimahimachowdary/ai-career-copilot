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
  Sparkles,
  AlertCircle,
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
      <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-md">
        <CardContent className="p-5">
          <form onSubmit={handleRunSearch} className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="h-4 w-4 absolute left-3 top-3 text-slate-500" />
              <Input
                placeholder="Target Job Title (e.g. Senior Backend Engineer, Data Scientist)..."
                value={roleQuery}
                onChange={(e) => setRoleQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            <div className="relative w-full sm:w-64">
              <MapPin className="h-4 w-4 absolute left-3 top-3 text-slate-500" />
              <Input
                placeholder="Location filter (optional)..."
                value={locationQuery}
                onChange={(e) => setLocationQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            <Button type="submit" variant="gradient" disabled={isLoading} className="shrink-0 w-full sm:w-auto">
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
        <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-sm text-rose-300">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          <div>
            <span className="font-semibold">Market Intelligence Agent Error: </span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Sub-tabs Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-2 sm:grid-cols-5 w-full">
          <TabsTrigger value="overview" className="text-xs">
            <PieChart className="h-3.5 w-3.5 mr-1.5 text-blue-400" />
            Role Overview
          </TabsTrigger>
          <TabsTrigger value="salary" className="text-xs">
            <DollarSign className="h-3.5 w-3.5 mr-1.5 text-emerald-400" />
            Salary Spectrum
          </TabsTrigger>
          <TabsTrigger value="skills" className="text-xs">
            <Flame className="h-3.5 w-3.5 mr-1.5 text-rose-400" />
            Skill Demand
          </TabsTrigger>
          <TabsTrigger value="heatmap" className="text-xs">
            <MapPin className="h-3.5 w-3.5 mr-1.5 text-indigo-400" />
            Geography
          </TabsTrigger>
          <TabsTrigger value="positioning" className="text-xs">
            <Compass className="h-3.5 w-3.5 mr-1.5 text-cyan-400" />
            My Positioning
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-2">
          <RoleOverview overview={overviewData} />
        </TabsContent>

        <TabsContent value="salary" className="pt-2">
          <SalaryChart
            salaryBand={salaryData?.salary_band || overviewData?.salary_band}
            topPayingCompanies={salaryData?.top_paying_companies}
            narrative={salaryData?.narrative}
          />
        </TabsContent>

        <TabsContent value="skills" className="pt-2">
          <TrendingSkills
            skills={skillsData?.skills || overviewData?.top_skills}
            totalPostings={skillsData?.total_postings_analysed || overviewData?.total_postings}
            narrative={skillsData?.narrative}
          />
        </TabsContent>

        <TabsContent value="heatmap" className="pt-2">
          <DemandHeatmap
            locations={heatmapData?.locations || overviewData?.top_locations}
            hottestMarket={heatmapData?.hottest_market}
            narrative={heatmapData?.narrative}
          />
        </TabsContent>

        <TabsContent value="positioning" className="pt-2">
          <ResumePositioning positioning={positioningData} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
