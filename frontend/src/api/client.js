import axios from "axios"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1"

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000, // 30s default; LLM-heavy calls override per-request
})

// Request interceptor: attach bearer token safely
apiClient.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem("token")
      if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`
      }
    } catch {
      // localStorage may be unavailable in some sandboxes
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 and errors safely
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "An unexpected network error occurred."

    // Expired or invalid token: clean up and notify app without throwing raw sensitive data
    if (status === 401) {
      try {
        localStorage.removeItem("token")
        localStorage.removeItem("user")
        window.dispatchEvent(new CustomEvent("auth:expired"))
      } catch {
        // ignore storage errors
      }
    }

    // Never log raw request body (may contain passwords) or token
    console.error(`[API Error ${status || "Network"}] ${error.config?.method?.toUpperCase()} ${error.config?.url}:`, errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default apiClient
