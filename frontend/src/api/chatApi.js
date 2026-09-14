import apiClient from "./client"

export const chatApi = {
  // Send career query through Adaptive Intent Router
  sendQuery: async ({ query, resumeId, jobId, history = [] }) => {
    const response = await apiClient.post("/chat/query", {
      query,
      resume_id: resumeId || undefined,
      job_id: jobId || undefined,
      history,
    })
    return response.data
  },

  // Diagnostic: classify query intent only
  classifyIntent: async (query) => {
    const response = await apiClient.post("/chat/classify-intent", {
      query,
    })
    return response.data
  },
}
