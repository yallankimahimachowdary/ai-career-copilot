import { describe, it, expect } from "vitest"
import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { InterviewRubricRadar } from "@/components/coach/InterviewRubricRadar"
import { AnswerEvaluator } from "@/components/coach/AnswerEvaluator"
import { SkillGapReport } from "@/components/coach/SkillGapReport"
import { QuestionBank } from "@/components/coach/QuestionBank"

describe("InterviewRubricRadar Component", () => {
  it("renders SVG radar chart container with role=img and accessible aria-label", () => {
    const rubric = {
      technical_accuracy: 8.5,
      depth: 7.0,
      structure: 9.0,
      specificity: 6.5,
    }

    render(<InterviewRubricRadar rubric={rubric} />)

    const img = screen.getByRole("img", { name: /interview rubric assessment radar chart/i })
    expect(img).toBeInTheDocument()
  })

  it("renders accessible HTML table fallback with all 4 rubric dimensions", () => {
    const rubric = {
      technical_accuracy: 8.5,
      depth: 7.0,
      structure: 9.0,
      specificity: 6.5,
    }

    render(<InterviewRubricRadar rubric={rubric} />)

    const table = screen.getByRole("table", { name: /rubric dimension scores table/i })
    expect(table).toBeInTheDocument()
    expect(screen.getByText(/technical accuracy/i)).toBeInTheDocument()
    expect(screen.getByText("8.5")).toBeInTheDocument()
    expect(screen.getByText(/depth/i)).toBeInTheDocument()
    expect(screen.getByText("7.0")).toBeInTheDocument()
    expect(screen.getByText(/structure/i)).toBeInTheDocument()
    expect(screen.getByText("9.0")).toBeInTheDocument()
    expect(screen.getByText(/specificity/i)).toBeInTheDocument()
    expect(screen.getByText("6.5")).toBeInTheDocument()
  })

  it("gracefully handles empty or null rubric object without throwing", () => {
    const { container } = render(<InterviewRubricRadar rubric={{}} />)

    expect(screen.getByText(/No rubric dimensions available to render/i)).toBeInTheDocument()
    expect(container).toBeInTheDocument()

    const { container: nullContainer } = render(<InterviewRubricRadar rubric={null} />)
    expect(nullContainer).toBeInTheDocument()
  })
})

describe("AnswerEvaluator Component", () => {
  it("embeds InterviewRubricRadar alongside score, grade, and feedback lists", () => {
    const evaluation = {
      score: 8.2,
      grade: "excellent",
      strengths: ["Clear explanation of event loop", "Used STAR structure"],
      weaknesses: ["Could include memory trade-offs"],
      rubric_breakdown: {
        technical_accuracy: 8.5,
        depth: 8.0,
        structure: 8.5,
        specificity: 7.8,
      },
    }

    render(<AnswerEvaluator evaluation={evaluation} />)

    expect(screen.getByText("8.2")).toBeInTheDocument()
    expect(screen.getByText("Excellent Answer")).toBeInTheDocument()
    expect(screen.getByRole("table", { name: /rubric dimension scores table/i })).toBeInTheDocument()
    expect(screen.getByText("Clear explanation of event loop")).toBeInTheDocument()
    expect(screen.getByText("Could include memory trade-offs")).toBeInTheDocument()
  })
})

describe("SkillGapReport Learning Resources", () => {
  it("renders clickable <a> tag when learning resource has a non-null URL", () => {
    const report = {
      job_title: "Backend Engineer",
      candidate_name: "Candidate",
      overall_readiness_score: 75,
      critical_gaps: [
        {
          skill: "FastAPI",
          category: "Framework",
          importance: "high",
          recommendation: "Review tutorial",
          learning_resources: [
            {
              title: "FastAPI Official Documentation",
              url: "https://fastapi.tiangolo.com",
              provider: "FastAPI",
            },
          ],
        },
      ],
    }

    render(<SkillGapReport report={report} activeResume={{ id: "res-1" }} />)

    const link = screen.getByRole("link", { name: /fastapi official documentation/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "https://fastapi.tiangolo.com")
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("renders plain text (no <a> tag) when learning resource has null URL", () => {
    const report = {
      job_title: "Backend Engineer",
      candidate_name: "Candidate",
      overall_readiness_score: 75,
      critical_gaps: [
        {
          skill: "Distributed Consensus",
          category: "Architecture",
          importance: "high",
          recommendation: "Read seminal papers",
          learning_resources: [
            {
              title: "Designing Data-Intensive Applications (Book)",
              url: null,
              provider: "O'Reilly",
            },
          ],
        },
      ],
    }

    render(<SkillGapReport report={report} activeResume={{ id: "res-1" }} />)

    expect(screen.getByText(/Designing Data-Intensive Applications/i)).toBeInTheDocument()
    expect(screen.queryByRole("link")).toBeNull()
  })
})

describe("QuestionBank Source Badges", () => {
  it("renders Corpus Retrieved badge for retrieved questions and Rule-Based Fallback for fallbacks", () => {
    const questionBank = {
      job_title: "Full Stack Engineer",
      technical_questions: [
        {
          id: "TQ-001",
          question: "Explain Python GIL?",
          target_skill: "Python",
          difficulty: "mid",
          source: "retrieved",
          sample_answer: "GIL ensures single thread execution in CPython.",
        },
        {
          id: "TQ-002",
          question: "Explain Docker containers?",
          target_skill: "Docker",
          difficulty: "junior",
          source: "rule_based_fallback",
          sample_answer: "Containers isolate application runtime.",
        },
      ],
    }

    render(<QuestionBank questionBank={questionBank} onPracticeQuestion={() => {}} />)

    expect(screen.getByText("Corpus Retrieved")).toBeInTheDocument()
    expect(screen.getByText("Rule-Based Fallback")).toBeInTheDocument()
  })

  it("toggles sample answer visibility when clicking show/hide model response", () => {
    const questionBank = {
      job_title: "Full Stack Engineer",
      technical_questions: [
        {
          id: "TQ-003",
          question: "Explain React Reconciliation?",
          target_skill: "React",
          sample_answer: "Virtual DOM diffing algorithm computes minimal updates.",
        },
      ],
    }

    render(<QuestionBank questionBank={questionBank} onPracticeQuestion={() => {}} />)

    expect(screen.queryByText(/Virtual DOM diffing algorithm/i)).toBeNull()

    const toggleBtn = screen.getByText("Show Model Response & Rubrics")
    fireEvent.click(toggleBtn)

    expect(screen.getByText(/Virtual DOM diffing algorithm/i)).toBeInTheDocument()
  })
})
