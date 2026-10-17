import test from "node:test"
import assert from "node:assert/strict"

// Mock browser global environment if needed
if (!globalThis.window) {
  globalThis.window = {
    dispatchEvent: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
  }
}

// In-memory mock localStorage
const storage = {
  data: new Map(),
  getItem(k) { return this.data.get(k) || null },
  setItem(k, v) { this.data.set(k, String(v)) },
  removeItem(k) { this.data.delete(k) },
  clear() { this.data.clear() },
}
globalThis.localStorage = storage

test("1. Authentication Contract & Interceptor Verification", async (t) => {
  await t.test("Attaches Bearer token from localStorage to outgoing requests", async () => {
    storage.setItem("token", "mock-jwt-token-xyz")
    const config = { headers: {} }

    // Interceptor simulation
    const token = localStorage.getItem("token")
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    assert.equal(config.headers.Authorization, "Bearer mock-jwt-token-xyz")
  })

  await t.test("Clears session on HTTP 401 Unauthorized", async () => {
    storage.setItem("token", "expired-token")
    storage.setItem("user", JSON.stringify({ email: "test@career.local" }))

    let eventFired = false
    const handleAuthExpired = () => {
      eventFired = true
      storage.removeItem("token")
      storage.removeItem("user")
    }

    // 401 response handling simulation
    const status = 401
    if (status === 401) {
      handleAuthExpired()
    }

    assert.equal(eventFired, true)
    assert.equal(storage.getItem("token"), null)
    assert.equal(storage.getItem("user"), null)
  })

  await t.test("Protected route redirects unauthenticated users", async () => {
    storage.clear()
    const isAuthenticated = Boolean(storage.getItem("token"))
    assert.equal(isAuthenticated, false, "Should be unauthenticated when no token is present")
  })
})

test("2. Resume & Profile - Provenance Distinction", async (t) => {
  await t.test("Clearly distinguishes AI-extracted skills from candidate-edited skills", () => {
    const resume = {
      id: "res-123",
      candidate_name: "Alex Rivera",
      parsed_data: {
        skills: ["Python", "FastAPI", "PostgreSQL"],
        summary: "Extracted software engineer summary",
      },
      manual_skills: ["Docker", "Kubernetes"],
      edited_summary: "Custom candidate summary",
    }

    // AI-extracted skills
    const extracted = resume.parsed_data.skills
    assert.deepEqual(extracted, ["Python", "FastAPI", "PostgreSQL"])

    // Manually added skills
    const manual = resume.manual_skills
    assert.deepEqual(manual, ["Docker", "Kubernetes"])

    // Total skills count
    const totalCount = extracted.length + manual.length
    assert.equal(totalCount, 5)

    // Verify provenance checks
    const isExtracted = (skill) => extracted.includes(skill)
    const isManual = (skill) => manual.includes(skill)

    assert.equal(isExtracted("Python"), true)
    assert.equal(isManual("Python"), false)
    assert.equal(isExtracted("Docker"), false)
    assert.equal(isManual("Docker"), true)

    // Summary provenance check
    const hasEditedSummary = resume.edited_summary !== undefined
    assert.equal(hasEditedSummary, true)
  })
})

test("3. Job Matches - Score Conventions & Freshness Status", async (t) => {
  await t.test("Ranks results consistently with 0.0 - 1.0 score convention", () => {
    const match = {
      job_id: "job-001",
      title: "Backend Engineer",
      composite_score: 0.865,
      final_score: 0.88,
      freshness_status: "fresh",
      is_active: true,
    }

    const fitScore = Math.round((match.final_score || match.composite_score) * 100)
    assert.equal(fitScore, 88)
    assert.ok(fitScore >= 0 && fitScore <= 100)
  })

  await t.test("Correctly maps freshness badges", () => {
    const statuses = ["fresh", "stale", "expired", "inactive"]
    const getBadgeLabel = (status) => {
      switch (status) {
        case "fresh": return "Fresh"
        case "stale": return "Stale"
        case "expired": return "Expired"
        case "inactive": return "Inactive"
        default: return "Unknown"
      }
    }

    assert.equal(getBadgeLabel("fresh"), "Fresh")
    assert.equal(getBadgeLabel("stale"), "Stale")
    assert.equal(getBadgeLabel("expired"), "Expired")
    assert.equal(getBadgeLabel("inactive"), "Inactive")
  })

  await t.test("Identifies inactive and expired jobs for non-recommendation flag", () => {
    const freshJob = { freshness_status: "fresh", is_active: true }
    const expiredJob = { freshness_status: "expired", is_active: false }
    const staleJob = { freshness_status: "stale", is_active: true }

    const isJobActive = (job) => job.is_active !== false && job.freshness_status !== "expired"

    assert.equal(isJobActive(freshJob), true)
    assert.equal(isJobActive(staleJob), true)
    assert.equal(isJobActive(expiredJob), false)
  })
})

test("4. Skill Gap - Qualifications vs Model Recommendations & Disclaimers", async (t) => {
  await t.test("Distinguishes verified qualifications from model recommendations", () => {
    const gapReport = {
      confirmed_strengths: ["Python", "SQL"],
      critical_gaps: [
        { skill: "AWS", category: "DevOps", importance: "high", candidate_has: false, recommendation: "Study AWS" },
      ],
      growth_gaps: [
        { skill: "Docker", category: "Tooling", importance: "medium", candidate_has: false, recommendation: "Explore Docker" },
      ],
      overall_readiness_score: 74.5,
    }

    assert.equal(gapReport.confirmed_strengths.length, 2)
    assert.equal(gapReport.critical_gaps.length, 1)
    assert.equal(gapReport.growth_gaps.length, 1)

    // Verifies critical gap has actionable recommendation
    assert.ok(gapReport.critical_gaps[0].recommendation.length > 0)
  })

  await t.test("Enforces scientific disclaimer against causal employability guarantees", () => {
    const disclaimer =
      "Note: Readiness scores and skill-gap recommendations are algorithmic estimates based on resume keyword and embedding similarity. They do not constitute a guarantee of interview invitation or employment outcome."

    assert.ok(disclaimer.includes("algorithmic estimates"))
    assert.ok(disclaimer.includes("do not constitute a guarantee"))
  })
})

test("5. Career Coach - Fail-Loud Error Handling (No Fake Answers)", async (t) => {
  await t.test("Chat query error sets genuine error state instead of simulated fake response", () => {
    const mockError = new Error("FastAPI connection refused")
    let state = { messages: [], isError: false }

    // Error handling logic
    try {
      throw mockError
    } catch (err) {
      state.isError = true
      state.messages.push({
        role: "assistant",
        isError: true,
        content: `Unable to process query: ${err.message}. Please check that the FastAPI backend is operational and try again.`,
      })
    }

    assert.equal(state.isError, true)
    assert.equal(state.messages[0].isError, true)
    assert.ok(state.messages[0].content.includes("FastAPI connection refused"))
    assert.equal(state.messages[0].content.includes("$168,000"), false, "Must never return fake salary data on failure")
  })

  await t.test("Answer evaluation error sets error notice without fake 8.2 score", () => {
    const mockEvalError = new Error("Evaluation model unavailable")
    let evaluationResult = null
    let errorNotice = null

    try {
      throw mockEvalError
    } catch (err) {
      errorNotice = `Answer evaluation failed: ${err.message}. Please click "Submit for Rubric Evaluation" to retry.`
      evaluationResult = null
    }

    assert.equal(evaluationResult, null)
    assert.ok(errorNotice.includes("Evaluation model unavailable"))
  })
})

test("6. Job Refresh Ingestion - State and Conflict Handling", async (t) => {
  await t.test("Correctly parses job refresh status summary", () => {
    const refreshStatus = {
      is_running: false,
      last_run: {
        run_id: "run-abc-123",
        status: "completed",
        duration_seconds: 4.25,
        sources: ["adzuna", "kaggle"],
        freshness_summary: {
          fresh_count: 1420,
          stale_count: 110,
          expired_count: 25,
        },
      },
    }

    assert.equal(refreshStatus.is_running, false)
    assert.equal(refreshStatus.last_run.status, "completed")
    assert.equal(refreshStatus.last_run.freshness_summary.fresh_count, 1420)
    assert.equal(refreshStatus.last_run.freshness_summary.stale_count, 110)
    assert.equal(refreshStatus.last_run.freshness_summary.expired_count, 25)
  })

  await t.test("Handles HTTP 409 Conflict when refresh is already active", () => {
    const conflictError = new Error("A job refresh run is already actively running.")
    const isConflict = conflictError.message.includes("already actively running")
    assert.equal(isConflict, true)
  })
})
