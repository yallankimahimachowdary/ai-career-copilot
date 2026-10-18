import { describe, it, expect, vi, beforeEach } from "vitest"
import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { IS_DEMO_MODE } from "@/App"
import { MatchesPage } from "@/pages/MatchesPage"
import { MarketPage } from "@/pages/MarketPage"
import { matchApi } from "@/api/matchApi"
import { marketApi } from "@/api/marketApi"
import { jobApi } from "@/api/jobApi"

vi.mock("@/api/matchApi", () => ({
  matchApi: {
    matchJobsForResume: vi.fn(),
  },
}))

vi.mock("@/api/marketApi", () => ({
  marketApi: {
    getRoleOverview: vi.fn(),
    getResumePositioning: vi.fn(),
  },
}))

vi.mock("@/api/jobApi", () => ({
  jobApi: {
    getStats: vi.fn().mockResolvedValue({ total: 1555 }),
  },
}))

describe("Honest Demo Mode Architecture", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("exports IS_DEMO_MODE boolean flag reflecting environment configuration", () => {
    expect(typeof IS_DEMO_MODE).toBe("boolean")
  })

  it("MatchesPage does not silently fall back to demoMatches on API failure when demo mode is off", async () => {
    matchApi.matchJobsForResume.mockRejectedValueOnce(new Error("503 Service Unavailable: Matcher offline"))

    render(
      <MemoryRouter>
        <MatchesPage activeResume={{ id: "res-real-001", isDemo: false }} />
      </MemoryRouter>
    )

    await waitFor(() => {
      // Must display honest matching service error, NOT demo jobs
      expect(screen.getByText(/Matching service unavailable:/i)).toBeInTheDocument()
      expect(screen.getByText(/503 Service Unavailable/i)).toBeInTheDocument()
      expect(screen.queryByText(/Demo Data/i)).toBeNull()
    })
  })

  it("MarketPage does not invent mock positioning data on API error when demo mode is off", async () => {
    marketApi.getRoleOverview.mockResolvedValueOnce({
      total_postings: 100,
      salary_band: { median_annual: 1200000 },
      top_skills: [],
    })
    marketApi.getResumePositioning.mockRejectedValueOnce(new Error("Database connection error"))

    render(
      <MemoryRouter>
        <MarketPage activeResume={{ id: "res-real-002", isDemo: false }} />
      </MemoryRouter>
    )

    await waitFor(() => {
      // Mock positioning (e.g. 72.0% coverage) must NOT be present
      expect(screen.queryByText("72.0%")).toBeNull()
    })
  })
})
