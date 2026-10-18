import React, { useState, useRef, useEffect } from "react"
import {
  X,
  Send,
  Bot,
  Loader2,
  Compass,
  ArrowRight,
  AlertCircle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { chatApi } from "@/api/chatApi"

export function CopilotChatDrawer({ activeResume, isOpen, onToggle }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I am your **AI Career Copilot** powered by the **Adaptive Query Intent Router**. Ask me anything about job matching, missing skills, interview preparation, or salary benchmarks!",
      router_decision: {
        intent: "JOB_SEARCH_AND_MATCH",
        strategy_selected: "Adaptive Intent Router Ready",
        confidence: null,
      },
      suggested_followups: [
        "What are the highest paying roles in my tech stack?",
        "Find jobs matching my resume",
        "Give me a senior backend interview question to practice",
        "What skills should I learn next?",
      ],
    },
  ])
  const [inputQuery, setInputQuery] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [expandedTraces, setExpandedTraces] = useState({})
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }

  useEffect(() => {
    if (isOpen) {
      scrollToBottom()
    }
  }, [messages, isOpen])

  const handleSend = async (queryText) => {
    const text = (queryText || inputQuery).trim()
    if (!text || isLoading) return

    setInputQuery("")
    const newHistory = [...messages, { role: "user", content: text }]
    setMessages(newHistory)
    setIsLoading(true)

    try {
      const response = await chatApi.sendQuery({
        query: text,
        resumeId: activeResume?.id,
        history: newHistory
          .filter((m) => !m.isError)
          .map((m) => ({ role: m.role, content: m.content })),
      })

      const trace = (response.sources || []).find((s) => s.type === "orchestrator_trace")
      const isDegraded = !!(
        response.degraded ||
        (trace && (trace.status?.startsWith("degraded") || (trace.errors && trace.errors.some((e) => !e.recovered))))
      )
      const degradedStatus = response.degraded || (trace ? trace.status : null) || (isDegraded ? "degraded" : null)

      const isMatchUnavailable = !!(
        response.match_unavailable ||
        (response.response && response.response.includes("Job matching is currently unavailable"))
      )

      const isNoMatchingJobs = !!(
        response.no_matching_jobs ||
        (response.response && response.response.includes("no matching jobs qualify"))
      )

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.response,
          router_decision: response.router_decision,
          sources: response.sources,
          actionable_recommendations: response.actionable_recommendations,
          suggested_followups: response.suggested_followups,
          execution_trace: response.execution_trace || trace,
          degraded: isDegraded ? degradedStatus : null,
          match_unavailable: isMatchUnavailable,
          no_matching_jobs: isNoMatchingJobs,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          isError: true,
          failedQuery: text,
          content: `Unable to process query: ${err.message}. Please check that the FastAPI backend is operational and try again.`,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      if (e.nativeEvent.isComposing) return // IME safe
      e.preventDefault()
      handleSend()
    }
  }

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        aria-label="Open AI Career Copilot Assistant"
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-3 rounded-full bg-[#7A2D4A] hover:bg-[#63233B] text-white shadow-lg hover:shadow-xl transition-all duration-200 group cursor-pointer"
      >
        <Bot className="h-5 w-5 text-white animate-bounce" />
        <span className="text-xs font-semibold tracking-wide">Ask Career Copilot</span>
        <span className="h-2 w-2 rounded-full bg-emerald-400" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[95vw] sm:w-[480px] h-[640px] max-h-[85vh] rounded-2xl bg-[#FAF7F3] border border-[#DDD6E7] shadow-2xl flex flex-col overflow-hidden font-sans">
      {/* Drawer Header */}
      <div className="p-3.5 border-b border-[#DDD6E7] bg-white flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-[#7A2D4A] text-white flex items-center justify-center">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[#3A3A52]">AI Career Copilot</span>
              <span className="text-[10px] font-mono bg-[#EDE7F6] text-[#7A2D4A] px-1.5 py-0.5 rounded font-medium">
                Adaptive Router
              </span>
            </div>
            <p className="text-[11px] text-[#5C5C7A]">Multi-turn career coaching & RAG assistant</p>
          </div>
        </div>

        <button
          onClick={onToggle}
          aria-label="Close Assistant"
          className="p-1.5 rounded-lg text-[#5C5C7A] hover:bg-[#EDE7F6] hover:text-[#3A3A52] transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex flex-col space-y-2 ${
              m.role === "user" ? "items-end" : "items-start"
            }`}
          >
            {/* Intent Router Strategy & Decision Badges */}
            {m.role === "assistant" && m.router_decision && (
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-[#5C5C7A]">
                <div className="flex items-center gap-1.5 bg-[#EDE7F6] px-2 py-0.5 rounded-full border border-[#DDD6E7]">
                  <Compass className="h-3 w-3 text-[#7A2D4A]" />
                  <span className="font-semibold text-[#7A2D4A]">
                    {m.router_decision.strategy_selected || m.router_decision.intent}
                  </span>
                  {m.router_decision.confidence != null && (
                    <span className="font-mono text-[#5C5C7A]">
                      ({Math.round(m.router_decision.confidence * 100)}% conf)
                    </span>
                  )}
                </div>

                {m.router_decision.backend && (
                  <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full border border-slate-200 capitalize font-medium">
                    Backend: {m.router_decision.backend}
                  </span>
                )}

                {m.router_decision.low_confidence && (
                  <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full border border-amber-300 font-semibold">
                    Low Confidence
                  </span>
                )}

                {m.router_decision.fallback_used && (
                  <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full border border-amber-300 font-semibold">
                    Fallback Used
                  </span>
                )}
              </div>
            )}

            {/* Degraded Execution Banner */}
            {m.role === "assistant" && (m.degraded || (m.execution_trace?.status?.startsWith("degraded"))) && (
              <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-900 flex items-start gap-2 max-w-[88%] shadow-xs">
                <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <strong className="font-semibold">Degraded Execution: </strong>
                  <span>{m.degraded || m.execution_trace?.status || "One or more agent nodes experienced a failure; fallback output provided."}</span>
                </div>
              </div>
            )}

            {/* Distinct Match Availability Notices */}
            {m.role === "assistant" && m.match_unavailable && (
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2 max-w-[88%] shadow-xs">
                <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                <span><strong>Notice:</strong> Job matching is currently unavailable in this session.</span>
              </div>
            )}

            {m.role === "assistant" && m.no_matching_jobs && !m.match_unavailable && (
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 flex items-start gap-2 max-w-[88%] shadow-xs">
                <Compass className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
                <span>No matching job postings found meeting current requirements.</span>
              </div>
            )}

            {/* Bubble Content */}
            {m.isError ? (
              <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 space-y-2 max-w-[90%] shadow-xs">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
                  <div className="flex-1 font-medium">{m.content}</div>
                </div>
                {m.failedQuery && (
                  <div className="pt-1 flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSend(m.failedQuery)}
                      disabled={isLoading}
                      className="text-xs h-7 border-red-300 text-red-800 hover:bg-red-100"
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      Retry Query
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div
                className={`p-3.5 rounded-2xl text-xs leading-relaxed max-w-[88%] shadow-xs ${
                  m.role === "user"
                    ? "bg-[#7A2D4A] text-white rounded-br-xs"
                    : "bg-white text-[#3A3A52] border border-[#DDD6E7] rounded-bl-xs"
                }`}
              >
                <div className="space-y-2">
                  {m.content.split("\n\n").map((block, bIdx) => {
                    const trimmed = block.trim()
                    if (trimmed.startsWith("### ")) {
                      return (
                        <h4 key={bIdx} className="font-bold text-sm text-[#7A2D4A] pt-1">
                          {trimmed.slice(4)}
                        </h4>
                      )
                    }
                    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                      const items = trimmed.split("\n").filter(Boolean)
                      return (
                        <ul key={bIdx} className="list-disc list-inside space-y-1 pl-1 text-[#3A3A52]">
                          {items.map((item, iIdx) => {
                            const clean = item.replace(/^[-*]\s+/, "")
                            const parts = clean.split(/(\*\*[^*]+\*\*)/g)
                            return (
                              <li key={iIdx}>
                                {parts.map((p, pIdx) =>
                                  p.startsWith("**") && p.endsWith("**") ? (
                                    <strong key={pIdx} className="font-semibold text-[#7A2D4A]">
                                      {p.slice(2, -2)}
                                    </strong>
                                  ) : (
                                    p
                                  )
                                )}
                              </li>
                            )
                          })}
                        </ul>
                      )
                    }
                    if (/^\d+\.\s+/.test(trimmed)) {
                      const items = trimmed.split("\n").filter(Boolean)
                      return (
                        <ol key={bIdx} className="list-decimal list-inside space-y-1 pl-1 text-[#3A3A52]">
                          {items.map((item, iIdx) => {
                            const clean = item.replace(/^\d+\.\s+/, "")
                            const parts = clean.split(/(\*\*[^*]+\*\*)/g)
                            return (
                              <li key={iIdx}>
                                {parts.map((p, pIdx) =>
                                  p.startsWith("**") && p.endsWith("**") ? (
                                    <strong key={pIdx} className="font-semibold text-[#7A2D4A]">
                                      {p.slice(2, -2)}
                                    </strong>
                                  ) : (
                                    p
                                  )
                                )}
                              </li>
                            )
                          })}
                        </ol>
                      )
                    }
                    const parts = trimmed.split(/(\*\*[^*]+\*\*)/g)
                    return (
                      <p key={bIdx}>
                        {parts.map((p, pIdx) =>
                          p.startsWith("**") && p.endsWith("**") ? (
                            <strong
                              key={pIdx}
                              className={m.role === "user" ? "font-bold text-white" : "font-semibold text-[#3A3A52]"}
                            >
                              {p.slice(2, -2)}
                            </strong>
                          ) : (
                            p
                          )
                        )}
                      </p>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Collapsible Execution Trace Panel */}
            {m.role === "assistant" && (m.execution_trace || (m.sources && m.sources.some((s) => s.type === "orchestrator_trace"))) && (() => {
              const trace = m.execution_trace || m.sources.find((s) => s.type === "orchestrator_trace")
              const isExpanded = !!expandedTraces[idx]
              return (
                <div className="max-w-[88%] w-full space-y-1">
                  <button
                    type="button"
                    onClick={() => setExpandedTraces((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                    className="flex items-center gap-1.5 text-[11px] font-mono text-[#5C5C7A] hover:text-[#7A2D4A] cursor-pointer"
                  >
                    <span>{isExpanded ? "Hide Execution Trace" : "View Execution Trace"}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#EDE7F6] text-[#7A2D4A] font-semibold">
                      {trace.status || "completed"}
                    </span>
                    {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>

                  {isExpanded && (
                    <div className="p-3 rounded-xl bg-[#FAF7F3] border border-[#DDD6E7] text-[11px] space-y-2 font-mono">
                      <div className="flex items-center justify-between text-[#3A3A52]">
                        <span>Backend: <strong>{trace.backend || "langgraph"}</strong></span>
                        <span>Status: <strong>{trace.status || "success"}</strong></span>
                      </div>

                      {trace.completed_nodes && trace.completed_nodes.length > 0 && (
                        <div>
                          <span className="text-[#5C5C7A] block text-[10px] uppercase font-semibold">Node Sequence:</span>
                          <div className="flex flex-wrap items-center gap-1 pt-0.5">
                            {trace.completed_nodes.map((node, nIdx) => (
                              <React.Fragment key={nIdx}>
                                <span className="px-1.5 py-0.5 rounded bg-white border border-[#DDD6E7] text-[#3A3A52]">
                                  {node}
                                </span>
                                {nIdx < trace.completed_nodes.length - 1 && <span className="text-[#5C5C7A]">➔</span>}
                              </React.Fragment>
                            ))}
                          </div>
                        </div>
                      )}

                      {trace.node_timings_ms && Object.keys(trace.node_timings_ms).length > 0 && (
                        <div>
                          <span className="text-[#5C5C7A] block text-[10px] uppercase font-semibold">Latency Timings:</span>
                          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 pt-0.5">
                            {Object.entries(trace.node_timings_ms).map(([node, ms]) => (
                              <div key={node} className="flex justify-between text-[#5C5C7A]">
                                <span>{node}:</span>
                                <span className="text-[#3A3A52] font-semibold">{ms}ms</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {trace.retries && Object.keys(trace.retries).length > 0 && (
                        <div>
                          <span className="text-[#5C5C7A] block text-[10px] uppercase font-semibold">Retries:</span>
                          <div className="flex flex-wrap gap-2 pt-0.5">
                            {Object.entries(trace.retries).map(([node, cnt]) => (
                              <span key={node} className="text-[#3A3A52]">
                                {node}: {cnt}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {trace.errors && trace.errors.length > 0 && (
                        <div className="space-y-1 pt-1 border-t border-[#DDD6E7]">
                          <span className="text-red-700 block text-[10px] uppercase font-semibold">Recorded Node Errors:</span>
                          {trace.errors.map((err, eIdx) => (
                            <div key={eIdx} className="text-[10px] text-red-700 bg-red-50 p-1.5 rounded border border-red-200">
                              <div><strong>{err.node || "agent"}:</strong> {err.message || err.error}</div>
                              {err.host_port && <div className="text-[9px] text-red-600">Endpoint: {err.host_port}</div>}
                              <div className="text-[9px]">Recovered: {err.recovered ? "Yes" : "No"}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Actionable Recommendations */}
            {m.actionable_recommendations && m.actionable_recommendations.length > 0 && (
              <div className="p-3 rounded-xl bg-white border border-[#DDD6E7] text-[11px] space-y-1 max-w-[88%] shadow-xs">
                <span className="font-semibold text-[#3A3A52] block">Actionable Next Steps:</span>
                <ul className="list-disc list-inside space-y-0.5 text-[#5C5C7A]">
                  {m.actionable_recommendations.map((rec, rIdx) => (
                    <li key={rIdx}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Suggested Followups */}
            {m.suggested_followups && m.suggested_followups.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1 max-w-[95%]">
                {m.suggested_followups.map((fu, fIdx) => (
                  <button
                    key={fIdx}
                    onClick={() => handleSend(fu)}
                    className="flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-full bg-white hover:bg-[#EDE7F6] text-[#3A3A52] hover:text-[#7A2D4A] transition-colors border border-[#DDD6E7] cursor-pointer shadow-xs"
                  >
                    <span>{fu}</span>
                    <ArrowRight className="h-2.5 w-2.5 opacity-60" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-white border border-[#DDD6E7] text-xs text-[#5C5C7A] w-fit shadow-xs">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#7A2D4A]" />
            <span>Evaluating query semantics & executing strategy...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-3 border-t border-[#DDD6E7] bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="flex items-center gap-2"
        >
          <Input
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about jobs, skill gaps, interview practice, salaries..."
            className="text-xs h-9 bg-white border-[#DDD6E7] text-[#3A3A52] focus:border-[#7A2D4A]"
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="sm"
            disabled={isLoading || !inputQuery.trim()}
            className="h-9 px-3 shrink-0 bg-[#7A2D4A] hover:bg-[#63233B] text-white"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </form>
      </div>
    </div>
  )
}

export default CopilotChatDrawer
