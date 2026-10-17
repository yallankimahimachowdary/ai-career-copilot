import React from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Loader2 } from "lucide-react"

export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#FAF7F3]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#7A2D4A]" />
          <p className="text-xs font-medium text-[#5C5C7A]">Verifying student session...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

export default ProtectedRoute
