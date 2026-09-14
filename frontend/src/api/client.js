import axios from "axios"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 60000, // 60s timeout for LLM inference calls
})

// Interceptor for response handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "An unexpected network error occurred."
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}:`, errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default apiClient
