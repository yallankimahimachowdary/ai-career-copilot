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
  searchSimilar: async (query, limit = 10) => {
    const response = await apiClient.post("/jobs/search/similar", {
      query,
      limit,
    })
    return response.data
  },
}
