import { describe, it, expect, beforeEach, vi } from "vitest"
import React from "react"
import { render, screen, act } from "@testing-library/react"
import { apiClient } from "@/api/client"
import { AuthProvider, useAuth } from "@/context/AuthContext"

function AuthConsumerTestComponent() {
  const { token, user, isAuthenticated, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth-state">{isAuthenticated ? "authenticated" : "anonymous"}</span>
      <span data-testid="token-val">{token || "none"}</span>
      <span data-testid="user-val">{user ? user.email : "none"}</span>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

describe("Real API Client & AuthContext Workflows", () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it("attaches Bearer token to request headers when token is in localStorage", async () => {
    localStorage.setItem("token", "real-jwt-token-xyz")
    const interceptor = apiClient.interceptors.request.handlers[0]

    const config = { headers: {} }
    const result = await interceptor.fulfilled(config)

    expect(result.headers.Authorization).toBe("Bearer real-jwt-token-xyz")
  })

  it("does not attach Authorization header when token is absent from localStorage", async () => {
    const interceptor = apiClient.interceptors.request.handlers[0]

    const config = { headers: {} }
    const result = await interceptor.fulfilled(config)

    expect(result.headers.Authorization).toBeUndefined()
  })

  it("does not overwrite existing Authorization header", async () => {
    localStorage.setItem("token", "real-jwt-token-xyz")
    const interceptor = apiClient.interceptors.request.handlers[0]

    const config = { headers: { Authorization: "Basic custom-creds" } }
    const result = await interceptor.fulfilled(config)

    expect(result.headers.Authorization).toBe("Basic custom-creds")
  })

  it("handles 401 response by removing token from localStorage", async () => {
    localStorage.setItem("token", "expired-token")
    localStorage.setItem("user", JSON.stringify({ email: "test@example.com" }))

    const interceptor = apiClient.interceptors.response.handlers[0]
    const error401 = {
      response: {
        status: 401,
        data: { detail: "Token expired or invalid" },
      },
      config: { method: "get", url: "/protected" },
    }

    await expect(interceptor.rejected(error401)).rejects.toThrow("Token expired or invalid")
    expect(localStorage.getItem("token")).toBeNull()
  })

  it("handles 401 response by removing user profile from localStorage", async () => {
    localStorage.setItem("token", "expired-token")
    localStorage.setItem("user", JSON.stringify({ email: "test@example.com" }))

    const interceptor = apiClient.interceptors.response.handlers[0]
    const error401 = {
      response: {
        status: 401,
        data: { detail: "Unauthorized" },
      },
      config: { method: "get", url: "/profile" },
    }

    await expect(interceptor.rejected(error401)).rejects.toThrow("Unauthorized")
    expect(localStorage.getItem("user")).toBeNull()
  })

  it("handles 401 response by dispatching auth:expired custom event on window", async () => {
    const expiredHandler = vi.fn()
    window.addEventListener("auth:expired", expiredHandler)

    const interceptor = apiClient.interceptors.response.handlers[0]
    const error401 = {
      response: {
        status: 401,
        data: { detail: "Session expired" },
      },
      config: { method: "post", url: "/matches" },
    }

    try {
      await interceptor.rejected(error401)
    } catch {
      // Expected rejection
    }

    expect(expiredHandler).toHaveBeenCalledTimes(1)
    window.removeEventListener("auth:expired", expiredHandler)
  })

  it("passes through successful responses unmodified", () => {
    const interceptor = apiClient.interceptors.response.handlers[0]
    const mockResponse = { data: { message: "ok" }, status: 200 }

    const result = interceptor.fulfilled(mockResponse)
    expect(result).toBe(mockResponse)
  })

  it("AuthProvider initializes token state from localStorage", () => {
    localStorage.setItem("token", "persisted-token-123")

    render(
      <AuthProvider>
        <AuthConsumerTestComponent />
      </AuthProvider>
    )

    expect(screen.getByTestId("token-val").textContent).toBe("persisted-token-123")
  })

  it("AuthProvider reacts to auth:expired event by resetting state and clearing storage", async () => {
    localStorage.setItem("token", "valid-init-token")

    render(
      <AuthProvider>
        <AuthConsumerTestComponent />
      </AuthProvider>
    )

    expect(screen.getByTestId("token-val").textContent).toBe("valid-init-token")

    act(() => {
      window.dispatchEvent(new CustomEvent("auth:expired"))
    })

    expect(screen.getByTestId("token-val").textContent).toBe("none")
    expect(screen.getByTestId("auth-state").textContent).toBe("anonymous")
    expect(localStorage.getItem("token")).toBeNull()
  })
})
