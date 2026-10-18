import { describe, it, expect, vi, beforeEach } from "vitest"
import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { TrendingSkills } from "@/components/market/TrendingSkills"
import { RolePathwayViewer } from "@/components/market/RolePathwayViewer"
import { graphApi } from "@/api/graphApi"

vi.mock("@/api/graphApi", () => ({
  graphApi: {
    getRolePathway: vi.fn(),
    getBridgeSkills: vi.fn(),
    getCareerPathway: vi.fn(),
  },
}))

describe("TrendingSkills Component Demand Share & Velocity", () => {
  it("renders Demand Share as percentage when demand_share is numeric", () => {
    const skills = [
      {
        skill: "Python",
        posting_count: 120,
        percentage: 45.0,
        trend_signal: "high",
        demand_share: 0.45,
        velocity: 1.25,
      },
    ]

    render(<TrendingSkills skills={skills} totalPostings={250} />)

    expect(screen.getByText("Python")).toBeInTheDocument()
    expect(screen.getByText("45.0%")).toBeInTheDocument()
    expect(screen.getByText("+1.25")).toBeInTheDocument()
  })

  it("renders Demand Share as N/A and Velocity as N/A (single baseline period) when null", () => {
    const skills = [
      {
        skill: "Rust",
        posting_count: 25,
        percentage: 10.0,
        trend_signal: "moderate",
        demand_share: null,
        velocity: null,
      },
    ]

    render(<TrendingSkills skills={skills} totalPostings={250} />)

    expect(screen.getByText("Rust")).toBeInTheDocument()
    expect(screen.getByText("N/A")).toBeInTheDocument()
    expect(screen.getByText("N/A (single baseline period)")).toBeInTheDocument()
  })

  it("renders empty state message when skills array is empty", () => {
    render(<TrendingSkills skills={[]} totalPostings={0} />)

    expect(screen.getByText(/No skill demand trends found for this query/i)).toBeInTheDocument()
  })
})

describe("RolePathwayViewer Component", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders starting role input and explore button", async () => {
    graphApi.getRolePathway.mockResolvedValueOnce({
      starting_role: "Junior Web Developer Trainee",
      total_reachable_roles: 0,
      pathways: [],
      summary: "No pathways found.",
    })

    render(<RolePathwayViewer defaultRole="Junior Web Developer Trainee" />)

    expect(screen.getByPlaceholderText(/enter starting role/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /explore career pathways/i })).toBeInTheDocument()
    })
  })

  it("renders progression hierarchy sequence and reachable roles", async () => {
    graphApi.getRolePathway.mockResolvedValueOnce({
      starting_role: "Junior Web Developer Trainee",
      total_reachable_roles: 1,
      summary: "Progression leads to Full Stack Engineer in ~2 years.",
      pathways: [
        {
          target_role: "Full Stack Engineer",
          target_family: "Engineering",
          target_level: "Mid",
          depth: 1,
          role_path: ["Junior Web Developer Trainee", "Full Stack Engineer"],
          transition_types: ["PROMOTION"],
          total_years: 2.0,
          required_skills: ["React", "TypeScript", "Node.js"],
          missing_skills: ["TypeScript"],
        },
      ],
    })

    render(<RolePathwayViewer defaultRole="Junior Web Developer Trainee" />)

    await waitFor(() => {
      expect(screen.getByText(/1 Reachable Roles Found/i)).toBeInTheDocument()
      expect(screen.getAllByText("Full Stack Engineer").length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText(/~2 yrs/i)).toBeInTheDocument()
      expect(screen.getByText("Depth 1")).toBeInTheDocument()
      expect(screen.getByText("React")).toBeInTheDocument()
      expect(screen.getAllByText("TypeScript").length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText("promotion")).toBeInTheDocument()
    })
  })

  it("displays knowledge graph error banner with retry button on query failure", async () => {
    graphApi.getRolePathway.mockRejectedValueOnce(new Error("Neo4j Bolt connection refused"))

    render(<RolePathwayViewer defaultRole="Failing Role" />)

    await waitFor(() => {
      expect(screen.getByText(/Knowledge Graph Query Error:/i)).toBeInTheDocument()
      expect(screen.getByText(/Neo4j Bolt connection refused/i)).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
    })
  })
})
