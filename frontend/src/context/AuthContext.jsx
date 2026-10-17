import React, { createContext, useContext, useState, useEffect, useCallback } from "react"
import { authApi } from "@/api/authApi"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem("token") || null
    } catch {
      return null
    }
  })
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authError, setAuthError] = useState(null)

  const logout = useCallback(() => {
    try {
      localStorage.removeItem("token")
      localStorage.removeItem("user")
    } catch {
      // ignore storage failure
    }
    setToken(null)
    setUser(null)
    setAuthError(null)
  }, [])

  // Verify session on mount if token is present
  useEffect(() => {
    let isMounted = true

    const initAuth = async () => {
      if (!token) {
        if (isMounted) setIsLoading(false)
        return
      }

      try {
        const userData = await authApi.getMe()
        if (isMounted) {
          setUser(userData)
          try {
            localStorage.setItem("user", JSON.stringify(userData))
          } catch {
            // ignore storage failure
          }
        }
      } catch (err) {
        // Token invalid or expired
        if (isMounted) {
          logout()
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    initAuth()

    // Listen for 401 expired token events from apiClient
    const handleAuthExpired = () => {
      logout()
    }
    window.addEventListener("auth:expired", handleAuthExpired)

    return () => {
      isMounted = false
      window.removeEventListener("auth:expired", handleAuthExpired)
    }
  }, [token, logout])

  const login = async ({ email, password }) => {
    setIsLoading(true)
    setAuthError(null)
    try {
      const data = await authApi.login({ email, password })
      const accessToken = data.access_token
      try {
        localStorage.setItem("token", accessToken)
      } catch {
        // ignore storage failure
      }
      setToken(accessToken)

      // Fetch user profile
      const userData = await authApi.getMe()
      setUser(userData)
      try {
        localStorage.setItem("user", JSON.stringify(userData))
      } catch {
        // ignore
      }
      return userData
    } catch (err) {
      const msg = err.message || "Invalid email or password."
      setAuthError(msg)
      throw new Error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const register = async ({ email, password, full_name }) => {
    setIsLoading(true)
    setAuthError(null)
    try {
      await authApi.register({ email, password, full_name })
      // Auto-login after registration
      return await login({ email, password })
    } catch (err) {
      const msg = err.message || "Registration failed. Please try again."
      setAuthError(msg)
      throw new Error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token && user),
    isLoading,
    authError,
    clearError: () => setAuthError(null),
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

export default AuthContext
