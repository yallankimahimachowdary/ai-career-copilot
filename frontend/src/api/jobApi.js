import apiClient from "./client"

export const jobApi = {
  // List job postings with pagination & filtering
  listJobs: async (params = {}) => {
    const response = await apiClient.get("/jobs", {
      params: {
        skip: params.skip || 0,
        limit: params.limit || 20,
        title: params.title || undefined,
        location: params.location || undefined,
        is_active: params.is_active !== undefined ? params.is_active : undefined,
        freshness: params.freshness || undefined,
      },
    })
    return response.data
  },

  // Get single job details
  getJob: async (jobId) => {
    const response = await apiClient.get(`/jobs/${jobId}`)
    return response.data
  },

  // Semantic search similar jobs
  searchSimilar: async (query, limit = 10, includeInactive = false) => {
    const response = await apiClient.post("/jobs/search/similar", {
      query,
      limit,
      include_inactive: includeInactive,
    })
    return response.data
  },

  // Get total postings stats count
  getStats: async () => {
    const response = await apiClient.get("/jobs/stats")
    return response.data
  },

  // Get job refresh and freshness evaluation status
  getRefreshStatus: async () => {
    const response = await apiClient.get("/jobs/refresh/status")
    return response.data
  },

  // Trigger manual job refresh & freshness evaluation
  triggerRefresh: async (payload = {}) => {
    const response = await apiClient.post("/jobs/refresh/run", payload)
    return response.data
  },
}

export default jobApi
