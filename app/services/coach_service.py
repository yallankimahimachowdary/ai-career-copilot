"""Coach Agent Service - Sprint 5.

Provides a 3-step coaching pipeline:
  Step 1: Skill-gap diagnostic analysis & learning roadmap
  Step 2: Curated question bank (technical, behavioral, gap-probing)
  Step 3: Rubric-based answer evaluation & interview readiness scoring

Uses Gemini as the primary LLM with a high-fidelity rule-based fallback
so that all automated tests pass without network access.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.coach import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    CoachQuestionBankRequest,
    FullCoachingSessionResponse,
    InterviewQuestion,
    QuestionBank,
    SkillGapItem,
    SkillGapReport,
)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_STOP_WORDS: set = {
    "a", "an", "the", "and", "or", "for", "in", "on", "at", "to", "of",
    "with", "by", "is", "are", "was", "be", "have", "has", "from", "that",
    "this", "it", "as", "we", "our", "your", "their", "will", "can", "may",
    "including", "experience", "skills", "knowledge", "ability", "work",
    "team", "strong", "must", "preferred", "required", "proven",
}

_CATEGORY_CODES: set = {
    "ART", "DSGN", "ADVR", "PRDM", "DIST", "EDU", "TRNG", "PRJM",
    "CNSL", "PRCH", "SUPL", "ANLS", "HCPR", "RSCH", "SCI", "GENB",
    "CUST", "STRA", "FIN", "OTHR", "LGL", "ENG", "QA", "BD",
    "IT", "ADM", "PROD", "MRKT", "PR", "WRT", "ACCT", "HR",
    "MNFC", "SALE", "MGMT",
}

# Regex skill taxonomy (mirrors matcher_service)
_SKILL_PATTERNS: Dict[str, str] = {
    "Python": r"\bpython\b",
    "Java": r"\bjava\b(?!\s*script)",
    "JavaScript": r"\b(javascript|js|ecmascript)\b",
    "TypeScript": r"\b(typescript|ts)\b",
    "C/C++": r"\b(c\+\+|c\s*programming|embedded\s*c)\b",
    "C#": r"\b(c#|c\s*sharp|\.net)\b",
    "SQL": r"\b(sql|mysql|postgresql|postgres|sqlite|pl\/sql)\b",
    "HTML/CSS": r"\b(html5?|css3?)\b",
    "React": r"\breact(?:\.js|js|\s*native)?\b",
    "FastAPI": r"\b(fastapi|fast\s*api)\b",
    "Django": r"\bdjango\b",
    "Flask": r"\bflask\b",
    "Spring Boot": r"\b(spring\s*boot|spring\s*framework)\b",
    "Node.js": r"\b(node(?:\.js|js)?)\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\b(kubernetes|k8s)\b",
    "AWS": r"\b(aws|amazon\s*web\s*services)\b",
    "Azure": r"\bazure\b",
    "GCP": r"\b(gcp|google\s*cloud)\b",
    "Git/GitHub": r"\b(git|github|gitlab)\b",
    "Linux": r"\b(linux|unix|ubuntu|centos)\b",
    "REST API": r"\b(rest(?:\s*api|\s*framework)?|restful|graphql|microservices)\b",
    "Machine Learning": r"\b(machine\s*learning|deep\s*learning|pytorch|tensorflow|keras|scikit.learn|nlp|computer\s*vision)\b",
    "Data Science": r"\b(data\s*science|data\s*analytics?|pandas|numpy|spark)\b",
    "Agile/Scrum": r"\b(agile|scrum|kanban|jira)\b",
    "Communication": r"\b(communication|collaboration|teamwork|interpersonal)\b",
    "Problem Solving": r"\b(problem.solving|analytical|critical\s*thinking)\b",
    "Leadership": r"\b(leadership|mentoring|team\s*lead)\b",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(s: str) -> str:
    """Lowercase and strip punctuation for fuzzy comparison."""
    return re.sub(r"[^a-z0-9\s/#+.]", "", s.lower()).strip()


def _extract_resume_skills(resume: Resume) -> List[str]:
    """Collect all skills from parsed_data (skills list + project technologies)."""
    pd = resume.parsed_data or {}
    raw: List[str] = list(pd.get("skills", []))
    for proj in pd.get("projects", []):
        for tech in proj.get("technologies", []):
            if isinstance(tech, str):
                raw.append(tech)
    return list(dict.fromkeys(
        s for s in raw if s and s.upper() not in _CATEGORY_CODES and len(s) > 1
    ))


def _extract_job_requirements(job: JobPosting) -> Dict[str, List[str]]:
    """Extract skill tokens from job description using regex taxonomy."""
    desc = (job.description or "") + " " + (job.skills_desc or "")
    desc_lower = desc.lower()

    found: List[str] = [
        skill for skill, pattern in _SKILL_PATTERNS.items()
        if re.search(pattern, desc_lower)
    ]

    if not found:
        # Fallback: raw keyword extraction
        for word in re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#./]{1,20}\b", desc):
            if word.upper() not in _CATEGORY_CODES and word.lower() not in _STOP_WORDS and len(word) > 2:
                found.append(word)
        found = list(dict.fromkeys(found))[:15]

    return {"must_have": found, "nice_to_have": []}


def _compute_readiness_score(
    confirmed: List[str],
    must_gaps: List[SkillGapItem],
    nice_gaps: List[SkillGapItem],
) -> float:
    """Compute a 0-100 readiness score."""
    n_conf = len(confirmed)
    n_must = len(must_gaps)
    n_nice = len(nice_gaps)
    total = n_conf + n_must * 3 + n_nice
    if total == 0:
        return 70.0
    return round(min(max((n_conf / total) * 100.0, 5.0), 98.0), 1)


def _skill_category(skill: str) -> str:
    s = skill.lower()
    if re.search(r"\b(python|java|javascript|typescript|c\+\+|c#|sql|html|css|ruby|php|go|swift|kotlin)\b", s):
        return "Language"
    if re.search(r"\b(react|django|flask|fastapi|spring|angular|vue|node|express|laravel)\b", s):
        return "Framework"
    if re.search(r"\b(docker|kubernetes|aws|azure|gcp|linux|devops|terraform)\b", s):
        return "DevOps / Cloud"
    if re.search(r"\b(machine learning|deep learning|pytorch|tensorflow|keras|nlp|data science|pandas|numpy)\b", s):
        return "AI / Data Science"
    if re.search(r"\b(git|github|gitlab|jira|agile|scrum)\b", s):
        return "Tooling / Workflow"
    if re.search(r"\b(communication|leadership|problem.solving|collaboration)\b", s):
        return "Soft Skill"
    return "Technical"


# ---------------------------------------------------------------------------
# Rule-based fallback implementations
# ---------------------------------------------------------------------------

def _rule_based_gap_report(
    resume: Resume,
    job: JobPosting,
    resume_skills: List[str],
    job_reqs: Dict[str, List[str]],
) -> SkillGapReport:
    """High-fidelity deterministic skill-gap report - no LLM required."""
    pd = resume.parsed_data or {}
    candidate_name: str = (
        pd.get("contact_info", {}).get("name") or resume.candidate_name or "Candidate"
    )
    job_title: str = job.title or "Role"
    company: Optional[str] = job.company_name

    resume_clean = {_clean(s) for s in resume_skills}

    confirmed_strengths: List[str] = []
    critical_gaps: List[SkillGapItem] = []
    growth_gaps: List[SkillGapItem] = []

    for skill in job_reqs.get("must_have", []):
        clean = _clean(skill)
        has = any(clean in rc or rc in clean for rc in resume_clean)
        if has:
            confirmed_strengths.append(skill)
        else:
            critical_gaps.append(
                SkillGapItem(
                    skill=skill,
                    category=_skill_category(skill),
                    importance="high",
                    candidate_has=False,
                    recommendation=f"Study {skill} via official documentation and build a small demo project.",
                )
            )

    for skill in job_reqs.get("nice_to_have", []):
        clean = _clean(skill)
        has = any(clean in rc or rc in clean for rc in resume_clean)
        if not has:
            growth_gaps.append(
                SkillGapItem(
                    skill=skill,
                    category=_skill_category(skill),
                    importance="medium",
                    candidate_has=False,
                    recommendation=f"Gain exposure to {skill} through tutorials or open-source contributions.",
                )
            )
        else:
            confirmed_strengths.append(skill)

    confirmed_strengths = list(dict.fromkeys(confirmed_strengths))
    score = _compute_readiness_score(confirmed_strengths, critical_gaps, growth_gaps)

    roadmap: List[str] = []
    for gap in critical_gaps[:3]:
        roadmap.append(f"Priority: {gap.recommendation}")
    for gap in growth_gaps[:2]:
        roadmap.append(f"Bonus: {gap.recommendation}")
    if not roadmap:
        roadmap.append("Practice communicating your existing projects using the STAR method.")

    n_gap = len(critical_gaps)
    n_str = len(confirmed_strengths)
    if n_gap == 0:
        summary = (
            f"{candidate_name} is a strong match for the {job_title} role with {n_str} confirmed skills. "
            f"Focus on deepening expertise and practising behavioral questions."
        )
    else:
        summary = (
            f"{candidate_name} demonstrates solid foundations for the {job_title} role with {n_str} matching skills. "
            f"There are {n_gap} critical gap(s) to address before the interview. "
            f"Following the learning roadmap below will significantly improve readiness."
        )

    return SkillGapReport(
        resume_id=str(resume.id),
        job_id=str(job.id),
        job_title=job_title,
        company_name=company,
        candidate_name=candidate_name,
        overall_readiness_score=score,
        confirmed_strengths=confirmed_strengths,
        critical_gaps=critical_gaps,
        growth_gaps=growth_gaps,
        executive_summary=summary,
        learning_roadmap=roadmap,
    )


# Technical question templates keyed by skill name
_TQ_TEMPLATES: Dict[str, Tuple[str, str, str]] = {
    "Python": (
        "Explain the difference between a list and a generator in Python, and when you would use each.",
        "Tests depth of Python knowledge and understanding of memory efficiency.",
        "A list stores all elements in memory; a generator yields elements lazily. Use generators for large data streams to reduce memory usage.",
    ),
    "Java": (
        "What is the difference between an abstract class and an interface in Java?",
        "Assesses understanding of OOP design principles.",
        "Abstract classes can have state and method implementations; interfaces define contracts. Use interfaces for multiple inheritance, abstract classes for shared base behavior.",
    ),
    "JavaScript": (
        "Explain event delegation in JavaScript and provide a use case.",
        "Tests DOM manipulation efficiency and understanding of event bubbling.",
        "Event delegation attaches a single listener to a parent element to handle events from its children, reducing memory overhead.",
    ),
    "SQL": (
        "Write a SQL query to find the second-highest salary from an employee table.",
        "Evaluates practical SQL query-writing ability.",
        "SELECT MAX(salary) FROM employees WHERE salary < (SELECT MAX(salary) FROM employees); or use DENSE_RANK().",
    ),
    "HTML/CSS": (
        "What is the CSS box model? How do padding, border, and margin differ?",
        "Foundational layout knowledge for front-end roles.",
        "Content -> Padding (inside border) -> Border -> Margin (outside). box-sizing: border-box includes padding and border in element width.",
    ),
    "React": (
        "Explain the difference between controlled and uncontrolled components in React.",
        "Tests understanding of React state management patterns.",
        "Controlled: form data in React state via onChange + value. Uncontrolled: data lives in DOM, accessed via refs. Prefer controlled for validation.",
    ),
    "Docker": (
        "What is the difference between a Docker image and a Docker container?",
        "Assesses DevOps fluency and containerization understanding.",
        "An image is an immutable template; a container is a running instance. Multiple containers can run from one image.",
    ),
    "Machine Learning": (
        "What is the bias-variance tradeoff, and how do you manage it?",
        "Evaluates ML conceptual understanding and practical tuning ability.",
        "High bias = underfitting; high variance = overfitting. Balance via regularization, cross-validation, and ensemble methods.",
    ),
    "Git/GitHub": (
        "What is the difference between git rebase and git merge?",
        "Tests understanding of Git workflows and collaboration practices.",
        "Merge preserves history with a merge commit; rebase rewrites commits for a linear history. Use rebase for clean feature branches.",
    ),
    "AWS": (
        "Describe how you would architect a fault-tolerant web application on AWS.",
        "Assesses cloud architecture knowledge.",
        "EC2 + Auto Scaling across multiple AZs, ALB for load balancing, RDS Multi-AZ, S3 + CloudFront for assets, CloudWatch for monitoring.",
    ),
    "TypeScript": (
        "What are the advantages of using TypeScript over plain JavaScript?",
        "Tests knowledge of static typing and compile-time safety benefits.",
        "TypeScript adds static typing, interfaces, and enums, catching errors at compile time. It improves IDE support and maintainability.",
    ),
    "REST API": (
        "Explain the difference between PUT and PATCH HTTP methods.",
        "Tests knowledge of HTTP semantics for RESTful API design.",
        "PUT replaces the entire resource; PATCH applies a partial update. Use PATCH when only a few fields change.",
    ),
    "FastAPI": (
        "How does FastAPI handle request validation, and what library does it use under the hood?",
        "Assesses framework-specific knowledge and Pydantic familiarity.",
        "FastAPI uses Pydantic models for automatic request/response validation, serialization, and OpenAPI schema generation.",
    ),
    "Django": (
        "Explain the difference between Django's ORM select_related and prefetch_related.",
        "Tests ORM optimization knowledge.",
        "select_related does a SQL JOIN for ForeignKey/OneToOne; prefetch_related does separate queries for ManyToMany, reducing N+1 issues.",
    ),
    "Data Science": (
        "Explain the difference between correlation and causation with an example.",
        "Tests statistical reasoning and data interpretation skills.",
        "Correlation measures the statistical relationship; causation implies direct cause. Ice cream sales and drowning are correlated but not causal.",
    ),
}


def _rule_based_question_bank(
    resume: Resume,
    job: JobPosting,
    gap_report: SkillGapReport,
    req: CoachQuestionBankRequest,
) -> QuestionBank:
    """Generate a deterministic question bank without LLM."""
    pd = resume.parsed_data or {}
    candidate_name: str = (
        pd.get("contact_info", {}).get("name") or resume.candidate_name or "Candidate"
    )
    projects: List[dict] = pd.get("projects", [])
    proj_context = (
        projects[0].get("name", "your project") if projects else "your most recent project"
    )

    technical_questions: List[InterviewQuestion] = []
    behavioral_questions: List[InterviewQuestion] = []
    gap_questions: List[InterviewQuestion] = []

    # --- Technical questions ---
    for skill in gap_report.confirmed_strengths:
        if len(technical_questions) >= req.max_technical:
            break
        tpl = _TQ_TEMPLATES.get(skill)
        if tpl:
            q, why, sample = tpl
            technical_questions.append(
                InterviewQuestion(
                    id=f"TQ-{len(technical_questions)+1:03d}",
                    category="technical",
                    difficulty="junior",
                    target_skill=skill,
                    question=q,
                    why_asked=why,
                    sample_answer=sample,
                    evaluation_criteria=[
                        "Correct and accurate explanation",
                        "Practical use-case mentioned",
                        "Code example or syntax awareness",
                    ],
                )
            )

    # Fallback generic questions
    _generic = [
        ("Problem Solving", "Walk me through how you debug a performance issue in a web application.", "mid"),
        ("System Design", "Design a URL shortener service. What components would you use?", "mid"),
        ("REST API", "Explain the difference between PUT and PATCH HTTP methods.", "junior"),
    ]
    for skill, q_text, diff in _generic:
        if len(technical_questions) >= req.max_technical:
            break
        technical_questions.append(
            InterviewQuestion(
                id=f"TQ-{len(technical_questions)+1:03d}",
                category="technical",
                difficulty=diff,  # type: ignore[arg-type]
                target_skill=skill,
                question=q_text,
                why_asked="Tests general software engineering knowledge.",
                sample_answer="Discuss the key difference with a concrete example relevant to the role.",
                evaluation_criteria=["Accurate explanation", "Concrete example", "Clear communication"],
            )
        )

    # --- Behavioral questions grounded in candidate projects ---
    _behavioral_templates = [
        (
            f'Tell me about a challenging technical problem you solved in "{proj_context}". Walk me through your approach.',
            "Assesses problem-solving process, resilience, and communication.",
            "Use STAR: describe the project, the specific technical blocker, steps you took, and what you achieved.",
        ),
        (
            "Describe a situation where you had to learn a new technology quickly to complete a project. How did you manage it?",
            "Evaluates learning agility and self-management.",
            "Pick a real project. Detail how you scoped the learning, practiced, and applied it under a deadline.",
        ),
        (
            "Give an example of when you collaborated with others on a technical project. What was your role and contribution?",
            "Gauges teamwork, communication, and ownership.",
            "Describe your contribution concretely. Mention any conflict resolution if relevant.",
        ),
        (
            "Tell me about a time you received critical feedback on your work. How did you respond?",
            "Tests growth mindset and professional maturity.",
            "Describe the feedback factually, how you took it constructively, and what specific change you made.",
        ),
    ]
    for i, (q_text, why, sample) in enumerate(_behavioral_templates[:req.max_behavioral]):
        behavioral_questions.append(
            InterviewQuestion(
                id=f"BQ-{i+1:03d}",
                category="behavioral",
                difficulty="junior",
                target_skill="Communication & Teamwork",
                question=q_text,
                why_asked=why,
                sample_answer=sample,
                evaluation_criteria=[
                    "Specific situation described (Situation)",
                    "Clear task or goal (Task)",
                    "Concrete actions taken (Action)",
                    "Measurable or qualitative outcome (Result)",
                ],
            )
        )

    # --- Gap-probing questions ---
    for i, gap in enumerate(gap_report.critical_gaps[:req.max_gap]):
        gap_questions.append(
            InterviewQuestion(
                id=f"GQ-{i+1:03d}",
                category="gap_probing",
                difficulty="junior",
                target_skill=gap.skill,
                question=(
                    f"This role requires {gap.skill}. While your resume doesn't list it explicitly, "
                    f"can you describe any exposure you've had, or how quickly you could get up to speed?"
                ),
                why_asked=(
                    f"Interviewers probe gaps to assess learning agility. "
                    f"{gap.skill} is a key requirement for this position."
                ),
                sample_answer=(
                    f"Be honest about your current level. Mention adjacent experience or transferable skills. "
                    f"Share a specific plan - a course, side project, or timeline - to demonstrate commitment."
                ),
                evaluation_criteria=[
                    "Honesty about current skill level",
                    "Adjacent skills or transferable experience mentioned",
                    "Specific learning plan or timeline provided",
                    "Positive and growth-oriented attitude",
                ],
            )
        )

    tips: List[str] = [
        f"Research {job.company_name or 'the company'} - their products, tech stack, and recent news before the interview.",
        "Prepare 2-3 STAR stories from your projects that demonstrate impact and problem-solving.",
        f"Review the {gap_report.job_title} job description and map each requirement to a concrete example from your background.",
        "Practice coding problems on platforms like LeetCode (Easy-Medium level) to warm up.",
        "Prepare thoughtful questions to ask the interviewer - this signals genuine interest.",
    ]

    return QuestionBank(
        resume_id=str(resume.id),
        job_id=str(job.id),
        job_title=gap_report.job_title,
        candidate_name=candidate_name,
        technical_questions=technical_questions,
        behavioral_questions=behavioral_questions,
        gap_questions=gap_questions,
        preparation_tips=tips,
    )


def _rule_based_evaluate_answer(req: AnswerEvaluationRequest) -> AnswerEvaluationResponse:
    """Score a candidate answer with deterministic heuristics."""
    answer = req.candidate_answer.strip()
    n_words = len(answer.split())
    rubric: Dict[str, float] = {}

    # Depth
    if n_words >= 150:
        rubric["depth"] = 8.5
    elif n_words >= 80:
        rubric["depth"] = 6.5
    elif n_words >= 40:
        rubric["depth"] = 4.5
    else:
        rubric["depth"] = 2.5

    # Structure (STAR keywords)
    star_hits = sum(
        1 for kw in [
            "situation", "task", "action", "result", "because", "therefore",
            " i ", " we ", "project", "team", "resolved", "achieved", "implemented",
        ]
        if kw in answer.lower()
    )
    rubric["structure"] = min(star_hits * 0.8, 8.5)

    # Technical accuracy
    skill_tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#/. ]{1,20}\b", req.target_skill.lower())
    tech_hits = sum(1 for t in skill_tokens if t.strip() in answer.lower())
    rubric["technical_accuracy"] = min(tech_hits * 3.0, 9.0) if skill_tokens else 5.0

    # Specificity (numbers, dates, project names)
    specificity_hits = len(
        re.findall(r"\d+|\b(?:project|version|feature|sprint|week|month|year)\b", answer.lower())
    )
    rubric["specificity"] = min(specificity_hits * 1.2, 8.0)

    score = round(sum(rubric.values()) / len(rubric), 1)
    score = min(max(score, 0.0), 10.0)

    if score >= 8.0:
        grade: str = "excellent"
    elif score >= 6.0:
        grade = "good"
    elif score >= 4.0:
        grade = "needs_improvement"
    else:
        grade = "poor"

    strengths: List[str] = []
    weaknesses: List[str] = []

    if rubric["depth"] >= 6.0:
        strengths.append("Answer has sufficient depth and detail.")
    else:
        weaknesses.append("Answer is too brief - aim for 80-150+ words to demonstrate depth.")

    if rubric["structure"] >= 5.0:
        strengths.append("Good use of structured narrative (STAR / logical flow).")
    else:
        weaknesses.append("Use the STAR method (Situation, Task, Action, Result) to structure behavioral answers.")

    if rubric["technical_accuracy"] >= 6.0:
        strengths.append(f"Demonstrates clear knowledge of {req.target_skill}.")
    else:
        weaknesses.append(f"Explicitly mention {req.target_skill} concepts to show technical competence.")

    if rubric["specificity"] >= 5.0:
        strengths.append("Good use of concrete examples, numbers, or dates.")
    else:
        weaknesses.append("Add specific metrics, timelines, or project names to make your answer more credible.")

    improved = (
        f"A strong answer would open with a brief context (Situation), define your goal or challenge (Task), "
        f"describe the specific steps you took mentioning {req.target_skill} explicitly (Action), "
        f"and close with a quantified or qualitative outcome (Result). "
        f"Aim for 120-150 words with at least one concrete example."
    )

    return AnswerEvaluationResponse(
        score=score,
        grade=grade,  # type: ignore[arg-type]
        strengths=strengths,
        weaknesses=weaknesses,
        improved_answer=improved,
        rubric_breakdown=rubric,
    )


# ---------------------------------------------------------------------------
# CoachAgent - main entry point
# ---------------------------------------------------------------------------

class CoachAgent:
    """3-step AI interview coaching agent."""

    def __init__(self) -> None:
        self.gemini_key: Optional[str] = settings.GEMINI_API_KEY
        self.gemini_model: str = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_key: Optional[str] = settings.OPENAI_API_KEY

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def generate_skill_gap_report(
        self, resume: Resume, job: JobPosting
    ) -> SkillGapReport:
        """Step 1: Produce a skill-gap diagnostic report."""
        resume_skills = _extract_resume_skills(resume)
        job_reqs = _extract_job_requirements(job)

        if self.gemini_key:
            try:
                return await self._gemini_skill_gap(resume, job, resume_skills, job_reqs)
            except Exception as exc:
                logger.warning(f"Gemini skill-gap failed: {exc}. Using rule-based fallback.")

        return _rule_based_gap_report(resume, job, resume_skills, job_reqs)

    async def generate_question_bank(
        self,
        resume: Resume,
        job: JobPosting,
        gap_report: SkillGapReport,
        req: CoachQuestionBankRequest,
    ) -> QuestionBank:
        """Step 2: Generate a curated question bank."""
        resume_skills = _extract_resume_skills(resume)

        if self.gemini_key:
            try:
                return await self._gemini_question_bank(resume, job, gap_report, req, resume_skills)
            except Exception as exc:
                logger.warning(f"Gemini question-bank failed: {exc}. Using rule-based fallback.")

        return _rule_based_question_bank(resume, job, gap_report, req)

    async def evaluate_candidate_answer(
        self, req: AnswerEvaluationRequest
    ) -> AnswerEvaluationResponse:
        """Step 3: Evaluate a practice answer with rubric scoring."""
        if self.gemini_key:
            try:
                return await self._gemini_evaluate_answer(req)
            except Exception as exc:
                logger.warning(f"Gemini answer eval failed: {exc}. Using rule-based fallback.")

        return _rule_based_evaluate_answer(req)

    async def run_full_session(
        self,
        resume: Resume,
        job: JobPosting,
        qb_req: CoachQuestionBankRequest,
    ) -> FullCoachingSessionResponse:
        """Run all three steps and return the combined coaching session."""
        gap_report = await self.generate_skill_gap_report(resume, job)
        question_bank = await self.generate_question_bank(resume, job, gap_report, qb_req)

        priorities: List[str] = [
            gap.recommendation for gap in gap_report.critical_gaps[:3]
        ]
        if not priorities:
            priorities = ["Practice STAR behavioral stories for your projects."]

        return FullCoachingSessionResponse(
            resume_id=str(resume.id),
            job_id=str(job.id),
            skill_gap_report=gap_report,
            question_bank=question_bank,
            overall_readiness_score=gap_report.overall_readiness_score,
            top_preparation_priorities=priorities,
        )

    # -----------------------------------------------------------------------
    # Gemini helpers
    # -----------------------------------------------------------------------

    async def _gemini_post(self, prompt: str) -> str:
        """Call Gemini generateContent and return raw text."""
        model_name = self.gemini_model.removeprefix("models/")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={self.gemini_key}"
        )
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _build_gap_prompt(
        self,
        resume: Resume,
        job: JobPosting,
        resume_skills: List[str],
        job_reqs: Dict[str, List[str]],
    ) -> str:
        pd_data = resume.parsed_data or {}
        edu_list = pd_data.get("education", [])
        edu_str = "; ".join(
            f"{e.get('degree','')} {e.get('field_of_study','')} @ {e.get('institution','')}"
            for e in edu_list
        )
        proj_list = pd_data.get("projects", [])
        proj_str = "; ".join(p.get("name", "") for p in proj_list)
        exp_list = pd_data.get("experience", [])
        exp_str = "; ".join(f"{e.get('title','')} @ {e.get('company','')}" for e in exp_list)
        must_have_str = ", ".join(job_reqs.get("must_have", []))[:500]
        desc_snippet = (job.description or "")[:800]
        candidate_name = pd_data.get("contact_info", {}).get("name") or resume.candidate_name
        return (
            "You are an expert career coach. Analyse the candidate profile against the job requirements "
            "and produce a JSON skill-gap report.\n\n"
            f"CANDIDATE:\n"
            f"Name: {candidate_name}\n"
            f"Skills: {', '.join(resume_skills[:40])}\n"
            f"Education: {edu_str}\n"
            f"Projects: {proj_str}\n"
            f"Experience: {exp_str}\n\n"
            f"JOB:\n"
            f"Title: {job.title}\n"
            f"Company: {job.company_name or 'N/A'}\n"
            f"Key Requirements: {must_have_str}\n"
            f"Description (excerpt): {desc_snippet}\n\n"
            "Return ONLY valid JSON matching this schema (no markdown fences):\n"
            "{\n"
            '  "overall_readiness_score": <0-100 float>,\n'
            '  "confirmed_strengths": ["skill1", "skill2"],\n'
            '  "critical_gaps": [{"skill": "...", "category": "...", "importance": "high", "candidate_has": false, "recommendation": "..."}],\n'
            '  "growth_gaps": [{"skill": "...", "category": "...", "importance": "medium", "candidate_has": false, "recommendation": "..."}],\n'
            '  "executive_summary": "2-3 sentence summary.",\n'
            '  "learning_roadmap": ["Step 1 ...", "Step 2 ..."]\n'
            "}"
        )

    async def _gemini_skill_gap(
        self,
        resume: Resume,
        job: JobPosting,
        resume_skills: List[str],
        job_reqs: Dict[str, List[str]],
    ) -> SkillGapReport:
        prompt = self._build_gap_prompt(resume, job, resume_skills, job_reqs)
        raw = await self._gemini_post(prompt)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        data = json.loads(raw)
        pd_data = resume.parsed_data or {}
        candidate_name = pd_data.get("contact_info", {}).get("name") or resume.candidate_name
        return SkillGapReport(
            resume_id=str(resume.id),
            job_id=str(job.id),
            job_title=job.title or "Role",
            company_name=job.company_name,
            candidate_name=candidate_name,
            overall_readiness_score=float(data.get("overall_readiness_score", 50.0)),
            confirmed_strengths=data.get("confirmed_strengths", []),
            critical_gaps=[SkillGapItem(**g) for g in data.get("critical_gaps", [])],
            growth_gaps=[SkillGapItem(**g) for g in data.get("growth_gaps", [])],
            executive_summary=data.get("executive_summary", ""),
            learning_roadmap=data.get("learning_roadmap", []),
        )

    def _build_question_bank_prompt(
        self,
        resume: Resume,
        job: JobPosting,
        gap_report: SkillGapReport,
        req: CoachQuestionBankRequest,
        resume_skills: List[str],
    ) -> str:
        pd_data = resume.parsed_data or {}
        proj_list = pd_data.get("projects", [])
        proj_str = "; ".join(
            f'{p.get("name","Project")}: {", ".join(p.get("technologies",[]))}'
            for p in proj_list
        )
        return (
            "You are an expert technical interviewer. Generate a question bank in JSON.\n\n"
            f"CANDIDATE STRENGTHS: {', '.join(gap_report.confirmed_strengths[:10])}\n"
            f"CRITICAL GAPS: {', '.join(g.skill for g in gap_report.critical_gaps[:5])}\n"
            f"CANDIDATE PROJECTS: {proj_str}\n"
            f"JOB TITLE: {gap_report.job_title}\n"
            f"COMPANY: {gap_report.company_name or 'N/A'}\n\n"
            f"Generate exactly: {req.max_technical} technical questions, {req.max_behavioral} behavioral questions, "
            f"{req.max_gap} gap-probing questions.\n\n"
            "Return ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "technical_questions": [{"id":"TQ-001","category":"technical","difficulty":"junior","target_skill":"...","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["..."]}],\n'
            '  "behavioral_questions": [{"id":"BQ-001","category":"behavioral","difficulty":"junior","target_skill":"Communication & Teamwork","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["Situation described","Task clear","Action concrete","Result stated"]}],\n'
            '  "gap_questions": [{"id":"GQ-001","category":"gap_probing","difficulty":"junior","target_skill":"...","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["Honesty","Adjacent skills","Learning plan","Growth mindset"]}],\n'
            '  "preparation_tips": ["Tip 1", "Tip 2", "Tip 3"]\n'
            "}"
        )

    async def _gemini_question_bank(
        self,
        resume: Resume,
        job: JobPosting,
        gap_report: SkillGapReport,
        req: CoachQuestionBankRequest,
        resume_skills: List[str],
    ) -> QuestionBank:
        prompt = self._build_question_bank_prompt(resume, job, gap_report, req, resume_skills)
        raw = await self._gemini_post(prompt)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        data = json.loads(raw)
        pd_data = resume.parsed_data or {}
        candidate_name = pd_data.get("contact_info", {}).get("name") or resume.candidate_name
        return QuestionBank(
            resume_id=str(resume.id),
            job_id=str(job.id),
            job_title=gap_report.job_title,
            candidate_name=candidate_name,
            technical_questions=[InterviewQuestion(**q) for q in data.get("technical_questions", [])],
            behavioral_questions=[InterviewQuestion(**q) for q in data.get("behavioral_questions", [])],
            gap_questions=[InterviewQuestion(**q) for q in data.get("gap_questions", [])],
            preparation_tips=data.get("preparation_tips", []),
        )

    def _build_evaluation_prompt(self, req: AnswerEvaluationRequest) -> str:
        return (
            "You are an expert technical interviewer evaluating a practice answer.\n\n"
            f"QUESTION: {req.question_text}\n"
            f"TARGET SKILL: {req.target_skill}\n"
            f"JOB CONTEXT: {req.job_context}\n"
            f"CANDIDATE ANSWER: {req.candidate_answer}\n\n"
            "Score from 0-10 and provide detailed feedback. Return ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "score": <0.0-10.0>,\n'
            '  "grade": "excellent|good|needs_improvement|poor",\n'
            '  "strengths": ["What the candidate did well"],\n'
            '  "weaknesses": ["What needs improvement"],\n'
            '  "improved_answer": "A polished model answer",\n'
            '  "rubric_breakdown": {"technical_accuracy": <0-10>, "depth": <0-10>, "structure": <0-10>, "specificity": <0-10>}\n'
            "}"
        )

    async def _gemini_evaluate_answer(self, req: AnswerEvaluationRequest) -> AnswerEvaluationResponse:
        prompt = self._build_evaluation_prompt(req)
        raw = await self._gemini_post(prompt)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        data = json.loads(raw)
        grade = data.get("grade", "needs_improvement")
        if grade not in ("excellent", "good", "needs_improvement", "poor"):
            grade = "needs_improvement"
        return AnswerEvaluationResponse(
            score=float(data.get("score", 5.0)),
            grade=grade,  # type: ignore[arg-type]
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            improved_answer=data.get("improved_answer", ""),
            rubric_breakdown={k: float(v) for k, v in data.get("rubric_breakdown", {}).items()},
        )


# Module-level singleton
coach_agent = CoachAgent()
