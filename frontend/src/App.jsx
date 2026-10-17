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

function AuthenticatedApp() {
  const [activeResume, setActiveResume] = useState(null)
  const [targetJobForCoach, setTargetJobForCoach] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

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
    try {
      const full = await resumeApi.getResume(demoResume.id)
      if (full) {
        setActiveResume({ ...full, isDemo: true })
        return
      }
    } catch {
      // fallback to local demo data
    }
    setActiveResume(demoResume)
  }

  return (
    <div className="flex h-screen bg-[#FAF7F3] text-[#3A3A52] overflow-hidden font-sans">
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
