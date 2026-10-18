import { describe, it, expect, vi } from "vitest"
import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { JobMatchCard } from "@/components/matches/JobMatchCard"
import { MatchDetailModal } from "@/components/matches/MatchDetailModal"
import { MatchDashboard } from "@/components/matches/MatchDashboard"

describe("JobMatchCard Component", () => {
  it("renders null company_name as Not specified", () => {
    const match = {
      job_id: "job-001",
      title: "Backend Engineer",
      company_name: null,
      location: "Bengaluru, Karnataka",
      final_score: 0.85,
    }

    render(<JobMatchCard match={match} onSelect={() => {}} />)

    expect(screen.getByText("Not specified")).toBeInTheDocument()
    expect(screen.getByText("Bengaluru, Karnataka")).toBeInTheDocument()
  })

  it("renders null location as Not specified", () => {
    const match = {
      job_id: "job-002",
      title: "Full Stack Developer",
      company_name: "Tech Solutions Pvt Ltd",
      location: null,
      final_score: 0.78,
    }

    render(<JobMatchCard match={match} onSelect={() => {}} />)

    expect(screen.getByText("Tech Solutions Pvt Ltd")).toBeInTheDocument()
    expect(screen.getByText("Not specified")).toBeInTheDocument()
  })

  it("renders valid company and location when provided", () => {
    const match = {
      job_id: "job-003",
      title: "ML Infrastructure Engineer",
      company_name: "DataCorp",
      location: "Hyderabad, Telangana",
      final_score: 0.91,
    }

    render(<JobMatchCard match={match} onSelect={() => {}} />)

    expect(screen.getByText("DataCorp")).toBeInTheDocument()
    expect(screen.getByText("Hyderabad, Telangana")).toBeInTheDocument()
    expect(screen.getByText("91%")).toBeInTheDocument()
    expect(screen.getByText("#1")).toBeInTheDocument()
  })

  it("renders matched skills and critical gap skills", () => {
    const match = {
      job_id: "job-004",
      title: "Cloud Architect",
      company_name: "CloudScale",
      location: "Remote",
      final_score: 0.82,
      skills_breakdown: {
        matched_skills: ["AWS", "Docker", "Python"],
        missing_must_have: ["Kubernetes", "Terraform"],
      },
    }

    render(<JobMatchCard match={match} onSelect={() => {}} />)

    expect(screen.getByText("AWS")).toBeInTheDocument()
    expect(screen.getByText("Docker")).toBeInTheDocument()
    expect(screen.getByText("Kubernetes")).toBeInTheDocument()
    expect(screen.getByText("Terraform")).toBeInTheDocument()
  })

  it("triggers onSelect callback when clicking Explain Fit & SHAP", () => {
    const onSelect = vi.fn()
    const match = {
      job_id: "job-005",
      title: "Data Engineer",
      company_name: "FinTech Hub",
      location: "Mumbai",
      final_score: 0.88,
    }

    render(<JobMatchCard match={match} onSelect={onSelect} />)

    const button = screen.getByRole("button", { name: /explain fit & shap/i })
    fireEvent.click(button)

    expect(onSelect).toHaveBeenCalledWith(match)
  })
})

describe("MatchDetailModal Component", () => {
  it("renders null company_name and null location as Not specified in modal header", () => {
    const match = {
      job_id: "job-006",
      title: "Site Reliability Engineer",
      company_name: null,
      location: null,
      final_score: 0.84,
      xgboost_score: 0.82,
      composite_score: 0.86,
    }

    render(
      <MemoryRouter>
        <MatchDetailModal match={match} open={true} onOpenChange={() => {}} />
      </MemoryRouter>
    )

    const notSpecifiedElements = screen.getAllByText("Not specified")
    expect(notSpecifiedElements.length).toBeGreaterThanOrEqual(2)
  })
})

describe("MatchDashboard Component Honest States", () => {
  it("renders Matching Unavailable banner when matchUnavailable prop is true", () => {
    render(
      <MemoryRouter>
        <MatchDashboard
          matches={[]}
          activeResume={{ id: "res-001" }}
          matchUnavailable={true}
          onRunMatch={() => {}}
        />
      </MemoryRouter>
    )

    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByText(/Matching Unavailable:/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Job matching is currently unavailable/i)
    ).toBeInTheDocument()
  })

  it("renders distinct catalog-level no matching jobs message when noMatchingJobs is true", () => {
    render(
      <MemoryRouter>
        <MatchDashboard
          matches={[]}
          activeResume={{ id: "res-002" }}
          noMatchingJobs={true}
          onRunMatch={() => {}}
        />
      </MemoryRouter>
    )

    expect(
      screen.getByText(/No matching jobs qualify for this profile in our database/i)
    ).toBeInTheDocument()
  })

  it("renders filter-specific empty message when user filters out all jobs", () => {
    const matches = [
      {
        job_id: "job-007",
        title: "Frontend Engineer",
        company_name: "Web Co",
        location: "Pune",
        final_score: 0.75,
      },
    ]

    render(
      <MemoryRouter>
        <MatchDashboard
          matches={matches}
          activeResume={{ id: "res-003" }}
          onRunMatch={() => {}}
        />
      </MemoryRouter>
    )

    const filterInput = screen.getByPlaceholderText(/filter location, company, role/i)
    fireEvent.change(filterInput, { target: { value: "NonExistentCity" } })

    expect(
      screen.getByText(/No matches found matching these filters/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Try lowering your minimum score threshold or clearing location filters/i)
    ).toBeInTheDocument()
  })

  it("renders list of ranked JobMatchCards when matches are provided", () => {
    const matches = [
      {
        job_id: "job-008",
        title: "Senior Backend Developer",
        company_name: "Tech Corp",
        location: "Bengaluru",
        final_score: 0.92,
      },
      {
        job_id: "job-009",
        title: "Backend Engineer II",
        company_name: "Infra Systems",
        location: "Remote",
        final_score: 0.81,
      },
    ]

    render(
      <MemoryRouter>
        <MatchDashboard
          matches={matches}
          activeResume={{ id: "res-004" }}
          onRunMatch={() => {}}
        />
      </MemoryRouter>
    )

    expect(screen.getByText("Senior Backend Developer")).toBeInTheDocument()
    expect(screen.getByText("Backend Engineer II")).toBeInTheDocument()
    expect(screen.getByText(/Displaying/i)).toBeInTheDocument()
    expect(screen.getByText("2")).toBeInTheDocument()
  })
})
