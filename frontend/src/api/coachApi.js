import apiClient from "./client"

export const coachApi = {
  // Step 1: Skill Gap Diagnostic
  getSkillGapReport: async (resumeId, jobId) => {
    const response = await apiClient.post("/coach/skill-gap", {
      resume_id: resumeId,
      job_id: jobId,
    })
    return response.data
  },

  // Step 2: Curated Interview Question Bank
  getQuestionBank: async (resumeId, jobId, options = {}) => {
    const response = await apiClient.post("/coach/question-bank", {
      resume_id: resumeId,
      job_id: jobId,
      max_technical: options.max_technical || 5,
      max_behavioral: options.max_behavioral || 3,
      max_gap: options.max_gap || 3,
    })
    return response.data
  },

  // Step 3: Evaluate Practice Answer
  evaluateAnswer: async ({ questionId, questionText, targetSkill, jobContext, candidateAnswer }) => {
    const response = await apiClient.post("/coach/evaluate-answer", {
      question_id: questionId || "Q-CUSTOM",
      question_text: questionText,
      target_skill: targetSkill,
      job_context: jobContext,
      candidate_answer: candidateAnswer,
    })
    return response.data
  },

  // Full Coaching Session (All steps)
  startFullSession: async (resumeId, jobId) => {
    const response = await apiClient.post("/coach/session", {
      resume_id: resumeId,
      job_id: jobId,
    })
    return response.data
  },
}
