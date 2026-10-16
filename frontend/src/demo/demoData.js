/**
 * DEMO DATA ONLY — Synthetic profiles and sample job matches for UI illustration.
 *
 * IMPORTANT:
 * - This file contains NO real personal identifiable information (PII) or production data.
 * - Used exclusively for offline development, component previews, and explicit demo exploration.
 */

export const isDemoData = true

export const demoResume = {
  id: "demo-resume-001",
  filename: "demo_software_engineer_resume.pdf",
  candidate_name: "Alex Morgan",
  email: "alex.morgan.demo@example.com",
  created_at: "2026-09-15T10:00:00Z",
  isDemo: true,
  parsed_data: {
    contact_info: {
      name: "Alex Morgan",
      email: "alex.morgan.demo@example.com",
      phone: "+1 (555) 019-2834",
      location: "San Francisco, CA",
      linkedin: "https://linkedin.com/in/demo-alex-morgan",
      github: "https://github.com/demo-alex-morgan",
    },
    skills: [
      "Python",
      "FastAPI",
      "SQL",
      "PostgreSQL",
      "Machine Learning",
      "PyTorch",
      "React",
      "JavaScript",
      "HTML/CSS",
      "Docker",
      "Git/GitHub",
      "REST API",
      "Data Science",
      "Pandas",
      "NumPy",
      "Scikit-Learn",
    ],
    experience: [
      {
        title: "Software Engineering Intern",
        company: "Demo Cloud Innovations",
        location: "San Francisco, CA",
        start_date: "2025-06",
        end_date: "2025-12",
        is_current: false,
        description: [
          "Developed high-throughput REST APIs using Python, FastAPI, and PostgreSQL with pgvector indexing.",
          "Implemented frontend user interfaces in React with real-time feedback and responsive layouts.",
          "Benchmarked search retrieval latency and optimized database query plans.",
        ],
      },
    ],
    education: [
      {
        degree: "B.S.",
        field_of_study: "Computer Science",
        institution: "State University of Technology (Demo)",
        start_date: "2021-08",
        end_date: "2025-05",
        gpa: "3.85",
      },
    ],
    projects: [
      {
        name: "AI Document Search Engine",
        technologies: ["Python", "FastAPI", "React", "PostgreSQL", "Docker"],
        description:
          "Full-stack semantic retrieval application featuring vector similarity indexing, hybrid re-ranking, and conversational interfaces.",
        link: "https://github.com/demo-alex-morgan/demo-project",
      },
    ],
    certifications: [
      {
        name: "Cloud Certified Associate (Demo)",
        issuer: "Cloud Certification Board",
        issue_date: "2025-03",
      },
    ],
  },
}

export const demoResumes = [demoResume]

export const demoMatches = [
  {
    job_id: "demo-job-001",
    title: "Full Stack Engineer (AI Platforms)",
    company_name: "Nexus Innovations (Demo)",
    location: "San Francisco, CA",
    remote_allowed: true,
    experience_level: "Mid-Senior",
    salary_range: "$130,000 - $160,000",
    final_score: 0.92,
    composite_score: 0.92,
    semantic_score: 0.89,
    keyword_score: 0.94,
    skills_breakdown: {
      matched_skills: ["Python", "FastAPI", "React", "Docker", "PostgreSQL", "REST API"],
      missing_skills: ["Kubernetes", "AWS"],
      match_ratio: 0.82,
    },
    shap_explanation: {
      base_value: 0.5,
      features: [
        { feature: "Python & FastAPI Fit", value: 0.18, description: "Strong core language and API framework alignment." },
        { feature: "Full-Stack Experience", value: 0.12, description: "Hands-on project work bridging React and backend services." },
        { feature: "Vector Search / ML", value: 0.08, description: "Familiarity with embeddings and retrieval workflows." },
        { feature: "Cloud Orchestration Gap", value: -0.05, description: "Role asks for Kubernetes container orchestration." },
      ],
      summary: "Excellent technical foundation with a 92% composite fit. Focus on cloud orchestration to close remaining requirements.",
    },
    isDemo: true,
  },
  {
    job_id: "demo-job-002",
    title: "Backend Software Engineer",
    company_name: "VectorStream Systems (Demo)",
    location: "Remote",
    remote_allowed: true,
    experience_level: "Associate / Junior",
    salary_range: "$105,000 - $130,000",
    final_score: 0.88,
    composite_score: 0.88,
    semantic_score: 0.86,
    keyword_score: 0.9,
    skills_breakdown: {
      matched_skills: ["Python", "PostgreSQL", "Docker", "SQL", "REST API", "Git/GitHub"],
      missing_skills: ["Kafka", "Redis"],
      match_ratio: 0.78,
    },
    shap_explanation: {
      base_value: 0.5,
      features: [
        { feature: "Data Engineering & SQL", value: 0.16, description: "Demonstrated relational database and query optimization skills." },
        { feature: "Backend Microservices", value: 0.14, description: "Clean API design patterns and containerization experience." },
        { feature: "Message Broker Gap", value: -0.04, description: "Streaming event pipelines with Kafka preferred." },
      ],
      summary: "Strong candidate for backend service implementation with 88% overall alignment.",
    },
    isDemo: true,
  },
]

export const demoJobs = [
  {
    id: "demo-job-001",
    job_id: "demo-job-001",
    title: "Full Stack Engineer (AI Platforms)",
    company_name: "Nexus Innovations (Demo)",
    location: "San Francisco, CA",
    remote_allowed: true,
    skills: ["Python", "FastAPI", "React", "Docker", "PostgreSQL"],
    fit_score: 92,
  },
  {
    id: "demo-job-002",
    job_id: "demo-job-002",
    title: "Backend Software Engineer",
    company_name: "VectorStream Systems (Demo)",
    location: "Remote",
    remote_allowed: true,
    skills: ["Python", "PostgreSQL", "Docker", "SQL"],
    fit_score: 88,
  },
]

// Backward-compatibility aliases
export const mockResumes = demoResumes
export const mockMatches = { matches: demoMatches }
export const mockJobs = demoJobs
