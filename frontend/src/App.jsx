import React, { useState, useEffect } from "react"
import { Routes, Route, Navigate, useNavigate } from "react-router-dom"
import { AuthProvider } from "@/context/AuthContext"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { LoginPage } from "@/pages/LoginPage"
import { RegisterPage } from "@/pages/RegisterPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { ResumePage } from "@/pages/ResumePage"
import { MatchesPage } from "@/pages/MatchesPage"
import { CoachPage } from "@/pages/CoachPage"
import { MarketPage } from "@/pages/MarketPage"
import { Sidebar } from "@/components/layout/Sidebar"
import { Header } from "@/components/layout/Header"
import { CopilotChatDrawer } from "@/components/chat/CopilotChatDrawer"
import { apiClient } from "@/api/client"
import { resumeApi } from "@/api/resumeApi"
import { demoResume } from "@/demo/demoData"

export const IS_DEMO_MODE =
  typeof import.meta !== "undefined" &&
  (import.meta.env?.VITE_DEMO_MODE === "true" || import.meta.env?.VITE_DEMO_MODE === true)

function AuthenticatedApp() {
  const [activeResume, setActiveResume] = useState(null)
  const [targetJobForCoach, setTargetJobForCoach] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [demoError, setDemoError] = useState(null)

  // Check backend health on initial mount and interval
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await apiClient.get("/health")
        if (res.data?.status === "healthy" || res.data?.status === "ok") {
          setIsConnected(true)
        }
      } catch {
        setIsConnected(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  const handleSelectDemo = async () => {
    setDemoError(null)
    if (!IS_DEMO_MODE) {
      try {
        const full = await resumeApi.getResume(demoResume.id)
        if (full) {
          setActiveResume({ ...full, isDemo: true })
          return
        }
      } catch (err) {
        console.error("Failed to load demo profile from backend API:", err)
        setDemoError(
          "Unable to load demo profile from backend: " +
            (err.message || "API request failed") +
            ". Real API mode is active; silent demo fallback is disabled."
        )
        return
      }
    } else {
      // Explicit demo mode enabled via VITE_DEMO_MODE=true
      setActiveResume(demoResume)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-[#FAF7F3] text-[#3A3A52] overflow-hidden font-sans">
      {/* Persistent Demo Mode Banner */}
      {IS_DEMO_MODE && (
        <div
          role="status"
          aria-label="Demo Mode Alert"
          className="bg-amber-500 text-stone-900 font-bold px-4 py-1.5 text-xs text-center border-b border-amber-600 shadow-xs flex items-center justify-center gap-2 shrink-0 z-50"
        >
          <span className="uppercase tracking-wider px-1.5 py-0.5 bg-stone-900 text-amber-300 rounded text-[10px]">
            DEMO MODE ACTIVE
          </span>
          <span>DEMO MODE: Using synthetic client-side data. Backend API calls are bypassed or simulated.</span>
        </div>
      )}

      {/* Honest Error Notification for Demo Profile Request */}
      {demoError && (
        <div
          role="alert"
          aria-label="Demo Load Error"
          className="bg-rose-100 text-rose-900 border-b border-rose-300 px-4 py-2 text-xs flex items-center justify-between shrink-0 z-50"
        >
          <span>{demoError}</span>
          <button
            onClick={() => setDemoError(null)}
            className="text-xs font-bold underline hover:text-rose-950 ml-4 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Left Navigation Sidebar */}
      <Sidebar
        isConnected={isConnected}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        <Header
          activeResume={activeResume}
          onSelectDemoResume={handleSelectDemo}
          isConnected={isConnected}
          onRefresh={() => window.location.reload()}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        />

        <main className="flex-1 pb-28">
          <Routes>
            <Route
              path="/dashboard"
              element={
                <DashboardPage
                  activeResume={activeResume}
                  onSelectDemoResume={handleSelectDemo}
                  onSelectJobForCoach={(job) => setTargetJobForCoach(job)}
                />
              }
            />
            <Route
              path="/resume"
              element={
                <ResumePage
                  activeResume={activeResume}
                  setActiveResume={setActiveResume}
                  isConnected={isConnected}
                />
              }
            />
            <Route
              path="/matches"
              element={
                <MatchesPage
                  activeResume={activeResume}
                  onSelectJobForCoach={(job) => setTargetJobForCoach(job)}
                />
              }
            />
            <Route
              path="/coach"
              element={
                <CoachPage
                  activeResume={activeResume}
                  targetJob={targetJobForCoach}
                />
              }
            />
            <Route
              path="/market"
              element={<MarketPage activeResume={activeResume} />}
            />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>

      {/* Interactive Adaptive RAG Career Copilot Assistant */}
      <CopilotChatDrawer
        activeResume={activeResume}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen(!isChatOpen)}
      />
      </div>
    </div>
  )
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AuthenticatedApp />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  )
}

export default App
