import apiClient from "./client"

export const coachApi = {
  // Step 1: Skill Gap Diagnostic — fully deterministic, returns in <1s
  getSkillGapReport: async (resumeId, jobId) => {
    const response = await apiClient.post(
      "/coach/skill-gap",
      { resume_id: resumeId, job_id: jobId },
      { timeout: 15000 } // 15s is more than enough for deterministic step
    )
    return response.data
  },

  // Step 2: Curated Interview Question Bank — Ollama, ~8-15s with num_predict cap
  getQuestionBank: async (resumeId, jobId, options = {}) => {
    const response = await apiClient.post(
      "/coach/question-bank",
      {
        resume_id: resumeId,
        job_id: jobId,
        max_technical: options.max_technical || 5,
        max_behavioral: options.max_behavioral || 3,
        max_gap: options.max_gap || 3,
      },
      { timeout: 90000 } // 90s for Ollama question generation
    )
    return response.data
  },

  // Step 3: Evaluate Practice Answer — Ollama with 350 token cap, ~5-8s
  evaluateAnswer: async ({ questionId, questionText, targetSkill, jobContext, candidateAnswer }) => {
    const response = await apiClient.post(
      "/coach/evaluate-answer",
      {
        question_id: questionId || "Q-CUSTOM",
        question_text: questionText,
        target_skill: targetSkill,
        job_context: jobContext,
        candidate_answer: candidateAnswer,
      },
      { timeout: 45000 } // 45s for answer evaluation
    )
    return response.data
  },

  // Full Coaching Session (Steps 1+2 combined) — kept for compatibility
  startFullSession: async (resumeId, jobId) => {
    const response = await apiClient.post(
      "/coach/session",
      { resume_id: resumeId, job_id: jobId },
      { timeout: 120000 } // 2min: Step 1 instant + Step 2 Ollama
    )
    return response.data
  },
}
