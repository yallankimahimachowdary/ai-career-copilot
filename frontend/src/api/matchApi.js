import apiClient from "./client"

export const matchApi = {
  // Find top matching jobs for a resume with SHAP XAI explanations
  matchJobsForResume: async (resumeId, params = {}) => {
    const response = await apiClient.post(
      `/matches/resume/${resumeId}`,
      {},
      {
        params: {
          limit: params.limit || 10,
          min_score: params.min_score || 0.0,
          location: params.location || undefined,
          remote_only: params.remote_only || false,
        },
      }
    )
    return response.data
  },

  // Find top matching candidates for a job
  matchCandidatesForJob: async (jobId, params = {}) => {
    const response = await apiClient.post(
      `/matches/job/${jobId}`,
      {},
      {
        params: {
          limit: params.limit || 10,
          min_score: params.min_score || 0.0,
        },
      }
    )
    return response.data
  },

  // Pairwise direct comparison between a resume and job
  compareMatch: async (resumeId, jobId) => {
    const response = await apiClient.get(`/matches/compare/${resumeId}/${jobId}`)
    return response.data
  },
}
