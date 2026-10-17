import React, { useState, useRef, useEffect } from "react"
import {
  X,
  Send,
  Sparkles,
  Bot,
  Loader2,
  Compass,
  ArrowRight,
  AlertCircle,
  RotateCcw,
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
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
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

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.response,
          router_decision: response.router_decision,
          sources: response.sources,
          actionable_recommendations: response.actionable_recommendations,
          suggested_followups: response.suggested_followups,
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
            {/* Intent Router Strategy Badge */}
            {m.role === "assistant" && m.router_decision && (
              <div className="flex items-center gap-1.5 text-[10px] text-[#5C5C7A] bg-[#EDE7F6] px-2 py-0.5 rounded-full border border-[#DDD6E7]">
                <Compass className="h-3 w-3 text-[#7A2D4A]" />
                <span className="font-semibold text-[#7A2D4A]">
                  {m.router_decision.strategy_selected || m.router_decision.intent}
                </span>
                {m.router_decision.confidence && (
                  <span className="font-mono text-[#5C5C7A]">
                    ({Math.round(m.router_decision.confidence * 100)}% conf)
                  </span>
                )}
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
