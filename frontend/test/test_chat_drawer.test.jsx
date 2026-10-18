import { describe, it, expect, vi, beforeEach } from "vitest"
import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { CopilotChatDrawer } from "@/components/chat/CopilotChatDrawer"
import { chatApi } from "@/api/chatApi"

vi.mock("@/api/chatApi", () => ({
  chatApi: {
    sendQuery: vi.fn(),
    classifyIntent: vi.fn(),
  },
}))

describe("CopilotChatDrawer Component", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders closed toggle button with Ask Career Copilot when isOpen is false", () => {
    const onToggle = vi.fn()
    render(<CopilotChatDrawer activeResume={null} isOpen={false} onToggle={onToggle} />)

    const button = screen.getByRole("button", { name: /open ai career copilot assistant/i })
    expect(button).toBeInTheDocument()
    expect(screen.getByText("Ask Career Copilot")).toBeInTheDocument()

    fireEvent.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it("renders open chat drawer with header when isOpen is true", () => {
    const onToggle = vi.fn()
    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={onToggle} />)

    expect(screen.getAllByText("AI Career Copilot").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Adaptive Router")).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/ask about jobs, skill gaps/i)).toBeInTheDocument()
  })

  it("renders close button and triggers onToggle callback", () => {
    const onToggle = vi.fn()
    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={onToggle} />)

    const closeBtn = screen.getByRole("button", { name: /close assistant/i })
    fireEvent.click(closeBtn)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it("renders initial welcome message with adaptive intent router ready badge", () => {
    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    expect(screen.getByText("Adaptive Intent Router Ready")).toBeInTheDocument()
    expect(screen.getByText(/I am your/i)).toBeInTheDocument()
  })

  it("renders suggested followups as clickable buttons and sends query on click", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "Here are some recommendations for your tech stack.",
      router_decision: {
        intent: "JOB_SEARCH",
        strategy_selected: "Hybrid Vector Search",
        confidence: 0.92,
        backend: "trained",
      },
      sources: [],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const followupBtn = screen.getByText("Find jobs matching my resume")
    fireEvent.click(followupBtn)

    await waitFor(() => {
      expect(chatApi.sendQuery).toHaveBeenCalledWith(
        expect.objectContaining({ query: "Find jobs matching my resume" })
      )
    })
  })

  it("renders router decision badges including backend, low confidence, and fallback used", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "Fallback recommendations provided.",
      router_decision: {
        intent: "CAREER_ADVICE",
        strategy_selected: "Heuristic Fallback Strategy",
        confidence: 0.35,
        backend: "heuristic",
        low_confidence: true,
        fallback_used: true,
      },
      sources: [],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Obscure query requiring fallback" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(screen.getByText("Backend: heuristic")).toBeInTheDocument()
      expect(screen.getByText("Low Confidence")).toBeInTheDocument()
      expect(screen.getByText("Fallback Used")).toBeInTheDocument()
      expect(screen.getByText("(35% conf)")).toBeInTheDocument()
    })
  })

  it("renders Degraded Execution warning banner when backend reports degraded status", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "Partial response generated with limited data.",
      router_decision: {
        intent: "JOB_SEARCH",
        strategy_selected: "Hybrid Vector Search",
        confidence: 0.85,
        backend: "trained",
      },
      degraded: "degraded: match node PostgreSQL connection timeout",
      sources: [],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Find jobs" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(screen.getByText(/Degraded Execution:/i)).toBeInTheDocument()
      expect(
        screen.getByText(/degraded: match node PostgreSQL connection timeout/i)
      ).toBeInTheDocument()
    })
  })

  it("renders distinct Match Unavailable notice when match_unavailable is true", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "⚠️ Job matching is currently unavailable. We could not retrieve aligned job postings at this time.",
      router_decision: {
        intent: "JOB_SEARCH",
        strategy_selected: "Hybrid Vector Search",
        confidence: 0.88,
        backend: "trained",
      },
      match_unavailable: true,
      sources: [],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Show me jobs" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(
        screen.getByText(/Job matching is currently unavailable in this session/i)
      ).toBeInTheDocument()
    })
  })

  it("renders distinct No Matching Jobs notice when no_matching_jobs is true", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "Search complete.",
      router_decision: {
        intent: "JOB_SEARCH",
        strategy_selected: "Hybrid Vector Search",
        confidence: 0.88,
        backend: "trained",
      },
      no_matching_jobs: true,
      sources: [],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Look for roles" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(
        screen.getByText(/No matching job postings found meeting current requirements/i)
      ).toBeInTheDocument()
    })
  })

  it("renders collapsible execution trace panel and expands details on click", async () => {
    chatApi.sendQuery.mockResolvedValueOnce({
      response: "Multi-agent orchestration executed.",
      router_decision: {
        intent: "JOB_SEARCH",
        strategy_selected: "Hybrid Vector Search",
        confidence: 0.90,
        backend: "trained",
      },
      sources: [
        {
          type: "orchestrator_trace",
          backend: "langgraph",
          status: "success",
          completed_nodes: ["route", "match", "synthesize"],
          node_timings_ms: { route: 12.5, match: 45.2, synthesize: 8.1 },
          retries: { match: 1 },
          errors: [
            {
              node: "match",
              message: "Temporary connection reset",
              host_port: "localhost:5432 (Postgres)",
              recovered: true,
            },
          ],
        },
      ],
    })

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Trace test query" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(screen.getByText("View Execution Trace")).toBeInTheDocument()
    })

    const traceBtn = screen.getByText("View Execution Trace")
    fireEvent.click(traceBtn)

    expect(screen.getByText("Node Sequence:")).toBeInTheDocument()
    expect(screen.getByText("route")).toBeInTheDocument()
    expect(screen.getByText("match")).toBeInTheDocument()
    expect(screen.getByText("synthesize")).toBeInTheDocument()

    expect(screen.getByText("Latency Timings:")).toBeInTheDocument()
    expect(screen.getByText("45.2ms")).toBeInTheDocument()

    expect(screen.getByText("Retries:")).toBeInTheDocument()
    expect(screen.getByText("match: 1")).toBeInTheDocument()

    expect(screen.getByText("Recorded Node Errors:")).toBeInTheDocument()
    expect(screen.getByText(/Temporary connection reset/i)).toBeInTheDocument()
    expect(screen.getByText(/Endpoint: localhost:5432 \(Postgres\)/i)).toBeInTheDocument()
  })

  it("handles network/API errors with retry button", async () => {
    chatApi.sendQuery.mockRejectedValueOnce(new Error("Connection refused to FastAPI service"))

    render(<CopilotChatDrawer activeResume={null} isOpen={true} onToggle={() => {}} />)

    const input = screen.getByPlaceholderText(/ask about jobs/i)
    fireEvent.change(input, { target: { value: "Failing query" } })
    fireEvent.submit(input.closest("form"))

    await waitFor(() => {
      expect(screen.getByText(/Connection refused to FastAPI service/i)).toBeInTheDocument()
      expect(screen.getByText("Retry Query")).toBeInTheDocument()
    })
  })
})
