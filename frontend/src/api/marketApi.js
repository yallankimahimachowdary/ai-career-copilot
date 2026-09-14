import apiClient from "./client"

export const marketApi = {
  // Salary Benchmarks
  getSalaryInsights: async (params = {}) => {
    const response = await apiClient.post("/market/salary-insights", {
      title_query: params.titleQuery || "Software Engineer",
      location: params.location || undefined,
      pay_period_filter: params.payPeriodFilter || "ALL",
    })
    return response.data
  },

  // Trending In-Demand Skills
  getTrendingSkills: async (params = {}) => {
    const response = await apiClient.post("/market/trending-skills", {
      title_query: params.titleQuery || undefined,
      location: params.location || undefined,
      top_n: params.topN || 10,
    })
    return response.data
  },

  // Geographic Demand Heatmap
  getDemandHeatmap: async (params = {}) => {
    const response = await apiClient.post("/market/demand-heatmap", {
      title_query: params.titleQuery || undefined,
      top_n: params.topN || 10,
    })
    return response.data
  },

  // Comprehensive Role Overview
  getRoleOverview: async (params = {}) => {
    const response = await apiClient.post("/market/role-overview", {
      title_query: params.titleQuery || "Software Engineer",
      location: params.location || undefined,
    })
    return response.data
  },

  // Personalized Resume Positioning
  getResumePositioning: async (resumeId) => {
    const response = await apiClient.post("/market/resume-positioning", {
      resume_id: resumeId,
    })
    return response.data
  },
}
