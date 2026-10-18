import apiClient from "./client"

export const graphApi = {
  // Query role progression pathways in Neo4j
  getRolePathway: async (roleName, candidateSkills = []) => {
    const params = new URLSearchParams()
    params.set("role_name", roleName)
    if (candidateSkills && candidateSkills.length > 0) {
      params.set("candidate_skills", candidateSkills.join(","))
    }
    const response = await apiClient.get(`/graph/role-pathway?${params.toString()}`)
    return response.data
  },

  // Query bridge skills between two roles
  getBridgeSkills: async (fromRole, toRole) => {
    const params = new URLSearchParams({
      from_role: fromRole,
      to_role: toRole,
    })
    const response = await apiClient.get(`/graph/bridge-skills?${params.toString()}`)
    return response.data
  },

  // Query 2-hop personalized candidate skill pathways
  getCareerPathway: async (candidateId) => {
    const response = await apiClient.get(`/graph/career-pathway/${candidateId}`)
    return response.data
  },
}

export default graphApi
