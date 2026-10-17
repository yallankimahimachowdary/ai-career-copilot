import apiClient from "./client"

export const authApi = {
  // Register a new student user
  register: async ({ email, password, full_name }) => {
    const response = await apiClient.post("/auth/register", {
      email,
      password,
      full_name,
    })
    return response.data
  },

  // Authenticate user credentials and receive JWT access token
  login: async ({ email, password }) => {
    const response = await apiClient.post("/auth/login", {
      email,
      password,
    })
    return response.data
  },

  // Fetch current authenticated user profile
  getMe: async () => {
    const response = await apiClient.get("/auth/me")
    return response.data
  },
}

export default authApi
