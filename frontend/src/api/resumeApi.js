import apiClient from "./client"

export const resumeApi = {
  // Upload and parse resume file
  uploadResume: async (file) => {
    const formData = new FormData()
    formData.append("file", file)
    const response = await apiClient.post("/resumes/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    })
    return response.data
  },

  // List parsed resumes
  listResumes: async (skip = 0, limit = 20) => {
    const response = await apiClient.get("/resumes", {
      params: { skip, limit },
    })
    return response.data
  },

  // Get single resume details
  getResume: async (resumeId) => {
    const response = await apiClient.get(`/resumes/${resumeId}`)
    return response.data
  },

  // Delete resume
  deleteResume: async (resumeId) => {
    const response = await apiClient.delete(`/resumes/${resumeId}`)
    return response.data
  },

  // Semantic search similar resumes
  searchSimilar: async (query, limit = 5) => {
    const response = await apiClient.post("/resumes/search/similar", {
      query,
      limit,
    })
    return response.data
  },
}
