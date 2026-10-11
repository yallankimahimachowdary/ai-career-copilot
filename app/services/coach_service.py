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
from sqlalchemy.ext.asyncio import AsyncSession

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

from app.core.taxonomy import (
    CANONICAL_SKILL_PATTERNS as _SKILL_PATTERNS,
    COMMON_STOP_WORDS as _STOP_WORDS,
    LINKEDIN_CATEGORY_CODES as _CATEGORY_CODES,
    SOFT_SKILLS as _SOFT_SKILLS,
)



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
    skills_list = job.skills if isinstance(job.skills, list) else []
    desc = (job.description or "") + " " + " ".join(str(s) for s in skills_list)
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

    must_have: List[str] = []
    nice_to_have: List[str] = []
    for s in found:
        if s.lower() in _SOFT_SKILLS:
            nice_to_have.append(s)
        else:
            must_have.append(s)

    return {"must_have": must_have, "nice_to_have": nice_to_have}



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
    if s in _SOFT_SKILLS or re.search(r"\b(communication|leadership|problem.solving|collaboration|teamwork|interpersonal|time management|critical thinking|mentoring)\b", s):
        return "Soft Skill"
    if re.search(r"\b(pharmacovigilance|regulatory affairs|gmp|glp|gcp|good manufacturing practice|clinical trials?|clinical research|drug formulation|drug discovery|medicinal chemistry|pharmacology)\b", s):
        return "Domain / Regulatory"
    if re.search(r"\b(pcr|qpcr|rt-pcr|gel electrophoresis|sds-page|cell culture|tissue culture|elisa|hplc|fplc|chromatography|flow cytometry|facs|autocad|solidworks|matlab|simulink|ansys|fea|cfd|catia|plc|scada|cnc|revit|bim|bioreactor|fermentation)\b", s):
        return "Lab / Engineering Tool"
    if re.search(r"\b(python|java|javascript|typescript|c\+\+|c#|sql|html|css|ruby|php|go|swift|kotlin|rust|r programming|r language|r stats)\b", s):
        return "Language"
    if re.search(r"\b(react|django|flask|fastapi|spring|angular|vue|node|express|laravel|graphql)\b", s):
        return "Framework"
    if re.search(r"\b(docker|kubernetes|aws|azure|gcp|linux|devops|terraform|ci/cd|jenkins|kafka|redis)\b", s):
        return "DevOps / Cloud"
    if re.search(r"\b(machine learning|deep learning|pytorch|tensorflow|keras|nlp|data science|pandas|numpy|bioinformatics|ngs|next-generation sequencing|crispr)\b", s):
        return "AI / Data Science"
    if re.search(r"\b(git|github|gitlab|jira|agile|scrum)\b", s):
        return "Tooling / Workflow"
    return "Technical"


def _generate_skill_advice(skill: str, category: Optional[str] = None) -> str:
    """Generate precise type-aware preparation advice without any LLM calls."""
    cat = category or _skill_category(skill)
    if cat == "Soft Skill":
        return f"Practise articulating STAR-format stories and run mock interviews highlighting {skill} in past collaborative projects."
    elif cat == "Domain / Regulatory":
        return f"Study relevant industry guidelines (or complete a short certificate course) for {skill}, and prepare a structured case study to discuss."
    elif cat == "Lab / Engineering Tool":
        return f"Engage in hands-on practice with {skill} via lab protocols or software tutorials, and prepare a worked example of your methodology."
    else:
        # Technical software / languages / frameworks / cloud
        return f"Complete a targeted crash course or documentation deep-dive in {skill}, and build a small reference project demonstrating core implementation."


def _generate_roadmap_step(gap: SkillGapItem, day_range: str, prefix: str) -> str:
    """Generate a type-aware 7-to-10 day learning roadmap step."""
    cat = gap.category
    skill = gap.skill
    if cat == "Soft Skill":
        action = f"Draft 2 STAR-method stories illustrating {skill} from your experience and rehearse behavioral interview delivery."
    elif cat == "Domain / Regulatory":
        action = f"Review standard regulatory frameworks/guidelines for {skill} and draft a concise 1-page compliance case study."
    elif cat == "Lab / Engineering Tool":
        action = f"Complete a practical tutorial or lab walkthrough for {skill} and document a step-by-step worked example."
    else:
        action = f"Work through official documentation/tutorials for {skill} and build a functioning demo project."

    return f"{day_range} ({prefix} - {cat}): {action}"


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

    # Process must-have requirements:
    # If a must-have is actually a soft skill, treat it as nice-to-have/growth gap
    for skill in job_reqs.get("must_have", []):
        clean = _clean(skill)
        has = any(clean in rc or rc in clean for rc in resume_clean)
        cat = _skill_category(skill)
        if has:
            confirmed_strengths.append(skill)
        else:
            if cat == "Soft Skill" or skill.lower() in _SOFT_SKILLS:
                growth_gaps.append(
                    SkillGapItem(
                        skill=skill,
                        category=cat,
                        importance="medium",
                        candidate_has=False,
                        recommendation=_generate_skill_advice(skill, cat),
                    )
                )
            else:
                critical_gaps.append(
                    SkillGapItem(
                        skill=skill,
                        category=cat,
                        importance="high",
                        candidate_has=False,
                        recommendation=_generate_skill_advice(skill, cat),
                    )
                )

    for skill in job_reqs.get("nice_to_have", []):
        clean = _clean(skill)
        has = any(clean in rc or rc in clean for rc in resume_clean)
        cat = _skill_category(skill)
        if not has:
            growth_gaps.append(
                SkillGapItem(
                    skill=skill,
                    category=cat,
                    importance="medium",
                    candidate_has=False,
                    recommendation=_generate_skill_advice(skill, cat),
                )
            )
        else:
            confirmed_strengths.append(skill)

    confirmed_strengths = list(dict.fromkeys(confirmed_strengths))
    score = _compute_readiness_score(confirmed_strengths, critical_gaps, growth_gaps)

    # 7-to-10 day roadmap ordered by real priority:
    # Critical technical gaps FIRST, followed by domain/tool gaps, then growth/soft skill polish
    roadmap: List[str] = []
    
    # Priority order for critical gaps: Technical / Cloud / Framework / AI first, then domain, then tools
    def _gap_priority_key(item: SkillGapItem) -> int:
        c = item.category
        if c in ("Technical", "Language", "Framework", "DevOps / Cloud", "AI / Data Science"):
            return 1
        if c == "Domain / Regulatory":
            return 2
        if c == "Lab / Engineering Tool":
            return 3
        return 4

    sorted_critical = sorted(critical_gaps, key=_gap_priority_key)
    sorted_growth = sorted(growth_gaps, key=_gap_priority_key)

    step_count = 0
    if len(sorted_critical) >= 1:
        step_count += 1
        roadmap.append(_generate_roadmap_step(sorted_critical[0], "Days 1–3", "Critical Gap"))
    if len(sorted_critical) >= 2:
        step_count += 1
        roadmap.append(_generate_roadmap_step(sorted_critical[1], "Days 4–6", "Critical Gap"))
    if len(sorted_critical) >= 3:
        step_count += 1
        roadmap.append(_generate_roadmap_step(sorted_critical[2], "Days 7–8", "Secondary Gap"))

    # Fill remaining days with growth gaps or soft skill interview polish
    if len(sorted_growth) > 0 and len(roadmap) < 4:
        next_growth = sorted_growth[0]
        day_label = f"Days {7 if len(roadmap) <= 2 else 9}–10"
        roadmap.append(_generate_roadmap_step(next_growth, day_label, "Growth Focus"))

    if not roadmap:
        roadmap.append("Days 1–5 (Technical Review): Deepen core domain expertise through reference projects.")
        roadmap.append("Days 6–10 (Behavioral Polish): Practise communicating your projects using the STAR method in mock interviews.")

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
# In-memory session cache keyed by (resume_id, job_id)
# ---------------------------------------------------------------------------

_GAP_CACHE: Dict[tuple, "SkillGapReport"] = {}
_QB_CACHE: Dict[tuple, "QuestionBank"] = {}
_MAX_CACHE_SIZE = 50  # evict oldest when full


def _cache_put(cache: dict, key: tuple, value: Any) -> None:
    if len(cache) >= _MAX_CACHE_SIZE:
        oldest = next(iter(cache))
        del cache[oldest]
    cache[key] = value


def invalidate_coach_cache(resume_id: str, job_id: Optional[str] = None) -> None:
    """Call after re-parsing a resume to clear stale cached reports."""
    keys_to_del = [
        k for k in list(_GAP_CACHE.keys()) + list(_QB_CACHE.keys())
        if k[0] == resume_id and (job_id is None or k[1] == job_id)
    ]
    for k in keys_to_del:
        _GAP_CACHE.pop(k, None)
        _QB_CACHE.pop(k, None)


# ---------------------------------------------------------------------------
# CoachAgent - main entry point
# ---------------------------------------------------------------------------

class CoachAgent:
    """3-step AI interview coaching agent.

    Step 1 (skill-gap) is fully deterministic — no LLM, returns in <100ms.
    Step 2 (question bank) uses Ollama with num_predict capping for speed.
    Step 3 (evaluate answer) uses Ollama with tight num_predict limit.
    Both Steps 1 and 2 are cached by (resume_id, job_id).
    """

    def __init__(self) -> None:
        self.ollama_base_url: Optional[str] = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
        self.gemini_key: Optional[str] = "ollama"  # Retained for fallback toggling and test compatibility
        self.openai_key: Optional[str] = settings.OPENAI_API_KEY

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def generate_skill_gap_report(
        self, resume: Resume, job: JobPosting
    ) -> SkillGapReport:
        """Step 1: Deterministic skill-gap diagnostic — no LLM needed, <100ms."""
        cache_key = (str(resume.id), str(job.id))
        if cache_key in _GAP_CACHE:
            logger.debug(f"Coach cache hit (skill-gap): {cache_key}")
            return _GAP_CACHE[cache_key]

        resume_skills = _extract_resume_skills(resume)
        job_reqs = _extract_job_requirements(job)
        report = _rule_based_gap_report(resume, job, resume_skills, job_reqs)

        _cache_put(_GAP_CACHE, cache_key, report)
        return report

    async def get_skill_gap_report(
        self, db: AsyncSession, resume_id: str, job_id: str
    ) -> SkillGapReport:
        """Fetch Resume and JobPosting from DB and produce a skill-gap report."""
        resume = await db.get(Resume, resume_id)
        job = await db.get(JobPosting, job_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found.")
        if not job:
            raise ValueError(f"Job posting {job_id} not found.")
        return await self.generate_skill_gap_report(resume, job)

    async def generate_question_bank(
        self,
        resume: Resume,
        job: JobPosting,
        gap_report: SkillGapReport,
        req: CoachQuestionBankRequest,
    ) -> QuestionBank:
        """Step 2: Generate a curated question bank (Ollama with num_predict cap)."""
        cache_key = (str(resume.id), str(job.id))
        if cache_key in _QB_CACHE:
            logger.debug(f"Coach cache hit (question-bank): {cache_key}")
            return _QB_CACHE[cache_key]

        resume_skills = _extract_resume_skills(resume)

        if self.ollama_base_url:
            try:
                qb = await self._ollama_question_bank(resume, job, gap_report, req, resume_skills)
                _cache_put(_QB_CACHE, cache_key, qb)
                return qb
            except Exception as exc:
                logger.warning(f"Ollama question-bank failed: {exc}. Using rule-based fallback.")

        qb = _rule_based_question_bank(resume, job, gap_report, req)
        _cache_put(_QB_CACHE, cache_key, qb)
        return qb

    async def evaluate_candidate_answer(
        self, req: AnswerEvaluationRequest
    ) -> AnswerEvaluationResponse:
        """Step 3: Evaluate a practice answer with rubric scoring."""
        if self.ollama_base_url:
            try:
                return await self._ollama_evaluate_answer(req)
            except Exception as exc:
                logger.warning(f"Ollama answer eval failed: {exc}. Using rule-based fallback.")

        return _rule_based_evaluate_answer(req)

    async def run_full_session(
        self,
        resume: Resume,
        job: JobPosting,
        qb_req: CoachQuestionBankRequest,
    ) -> FullCoachingSessionResponse:
        """Run Steps 1+2 and return the combined coaching session.
        Step 1 is deterministic (<100ms). Step 2 uses cached Ollama output.
        """
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
    # Ollama helpers
    # -----------------------------------------------------------------------

    def _clean_and_parse_json(self, text_content: str) -> dict:
        """Strip markdown fences, locate JSON delimiters, fix common syntax flaws/truncation, and parse."""
        cleaned = text_content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to extract the first balanced or partial JSON block
        start_idx = cleaned.find("{")
        if start_idx != -1:
            candidate = cleaned[start_idx:]
            # Remove trailing commas
            candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # Handle truncated JSON by attempting to close open brackets/braces
            open_braces = candidate.count("{") - candidate.count("}")
            open_brackets = candidate.count("[") - candidate.count("]")
            # Strip trailing incomplete key or partial token before closing
            repaired = re.sub(r',\s*"[^"]*"?\s*$', '', candidate)
            repaired = re.sub(r',\s*$', '', repaired)
            repaired += ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"Could not extract valid JSON from response: {text_content[:200]}")


    async def _ollama_post(self, prompt: str, max_attempts: int = 2, num_predict: int = 700) -> dict:
        """Call configured LLM provider (Ollama or Gemini) with JSON formatting and retry logic."""
        if hasattr(self, "_gemini_post") and self._gemini_post.__code__ != CoachAgent._gemini_post.__code__:
            raw = await self._gemini_post(prompt)
            if isinstance(raw, dict):
                return raw
            return self._clean_and_parse_json(str(raw))

        from app.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = await provider.generate_json(
                    prompt=prompt,
                    temperature=0.0,
                    max_tokens=num_predict,
                    keep_alive="30m",
                    timeout=60.0,
                )
                return resp.data
            except Exception as exc:
                last_error = exc
                logger.warning(f"Coach LLM call attempt {attempt}/{max_attempts} failed: {exc}")
                if attempt < max_attempts:
                    continue

        raise RuntimeError(f"Coach LLM call failed after {max_attempts} attempts: {last_error}")



    async def _gemini_post(self, prompt: str) -> str:
        """Compatibility wrapper for tests that mock _gemini_post."""
        data = await self._ollama_post(prompt)
        return json.dumps(data)

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

    async def _ollama_skill_gap(
        self,
        resume: Resume,
        job: JobPosting,
        resume_skills: List[str],
        job_reqs: Dict[str, List[str]],
    ) -> SkillGapReport:
        prompt = self._build_gap_prompt(resume, job, resume_skills, job_reqs)
        data = await self._ollama_post(prompt)
        pd_data = resume.parsed_data or {}
        candidate_name = pd_data.get("contact_info", {}).get("name") or resume.candidate_name

        score_val = data.get("overall_readiness_score", 50.0)
        try:
            score_val = float(score_val)
        except (ValueError, TypeError):
            score_val = 50.0

        raw_critical = data.get("critical_gaps", [])
        critical_items: List[SkillGapItem] = []
        for g in raw_critical:
            if isinstance(g, dict):
                critical_items.append(SkillGapItem(**g))
            elif isinstance(g, str):
                critical_items.append(SkillGapItem(
                    skill=g,
                    category=_skill_category(g),
                    importance="high",
                    candidate_has=False,
                    recommendation=f"Build practical experience with {g}."
                ))

        raw_growth = data.get("growth_gaps", [])
        growth_items: List[SkillGapItem] = []
        for g in raw_growth:
            if isinstance(g, dict):
                growth_items.append(SkillGapItem(**g))
            elif isinstance(g, str):
                growth_items.append(SkillGapItem(
                    skill=g,
                    category=_skill_category(g),
                    importance="medium",
                    candidate_has=False,
                    recommendation=f"Gain exposure to {g}."
                ))

        confirmed = data.get("confirmed_strengths", [])
        if not isinstance(confirmed, list):
            confirmed = [str(confirmed)] if confirmed else []

        roadmap = data.get("learning_roadmap", [])
        if not isinstance(roadmap, list):
            roadmap = [str(roadmap)] if roadmap else []

        return SkillGapReport(
            resume_id=str(resume.id),
            job_id=str(job.id),
            job_title=job.title or "Role",
            company_name=job.company_name,
            candidate_name=candidate_name,
            overall_readiness_score=score_val,
            confirmed_strengths=confirmed,
            critical_gaps=critical_items,
            growth_gaps=growth_items,
            executive_summary=str(data.get("executive_summary", "")),
            learning_roadmap=roadmap,
        )

    _gemini_skill_gap = _ollama_skill_gap

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
            "You are an expert technical interviewer. Return concise JSON with interview questions.\n\n"
            f"STRENGTHS: {', '.join(gap_report.confirmed_strengths[:6])}\n"
            f"GAPS: {', '.join(g.skill for g in gap_report.critical_gaps[:3])}\n"
            f"ROLE: {gap_report.job_title} at {gap_report.company_name or 'Tech'}\n\n"
            f"Generate {min(req.max_technical, 3)} technical, {min(req.max_behavioral, 2)} behavioral, {min(req.max_gap, 2)} gap questions.\n"
            "Keep each question and sample_answer to 1-2 sentences.\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "technical_questions": [{"id":"TQ-001","category":"technical","difficulty":"mid","target_skill":"...","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["..."]}],\n'
            '  "behavioral_questions": [{"id":"BQ-001","category":"behavioral","difficulty":"junior","target_skill":"Communication","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["..."]}],\n'
            '  "gap_questions": [{"id":"GQ-001","category":"gap_probing","difficulty":"junior","target_skill":"...","question":"...","why_asked":"...","sample_answer":"...","evaluation_criteria":["..."]}],\n'
            '  "preparation_tips": ["Tip 1", "Tip 2"]\n'
            "}"
        )

    async def _ollama_question_bank(
        self,
        resume: Resume,
        job: JobPosting,
        gap_report: SkillGapReport,
        req: CoachQuestionBankRequest,
        resume_skills: List[str],
    ) -> QuestionBank:
        prompt = self._build_question_bank_prompt(resume, job, gap_report, req, resume_skills)
        data = await self._ollama_post(prompt, max_attempts=1, num_predict=500)

        pd_data = resume.parsed_data or {}
        candidate_name = pd_data.get("contact_info", {}).get("name") or resume.candidate_name

        def _parse_q_list(raw_list: Any, default_cat: str) -> List[InterviewQuestion]:
            out = []
            if not isinstance(raw_list, list):
                return out
            for i, item in enumerate(raw_list):
                if isinstance(item, dict):
                    item.setdefault("id", f"{default_cat[:2].upper()}-{i+1:03d}")
                    item.setdefault("category", default_cat)
                    item.setdefault("difficulty", "junior")
                    item.setdefault("target_skill", "General")
                    item.setdefault("question", "Describe your experience.")
                    item.setdefault("why_asked", "Assesses relevant competency.")
                    item.setdefault("sample_answer", "Use the STAR method.")
                    item.setdefault("evaluation_criteria", ["Clear communication", "Relevance"])
                    out.append(InterviewQuestion(**item))
                elif isinstance(item, str):
                    out.append(InterviewQuestion(
                        id=f"{default_cat[:2].upper()}-{i+1:03d}",
                        category=default_cat,
                        difficulty="junior",
                        target_skill="General",
                        question=item,
                        why_asked="Assesses relevant competency.",
                        sample_answer="Use the STAR method.",
                        evaluation_criteria=["Clear communication", "Relevance"],
                    ))
            return out

        tq = _parse_q_list(data.get("technical_questions", []), "technical")
        bq = _parse_q_list(data.get("behavioral_questions", []), "behavioral")
        gq = _parse_q_list(data.get("gap_questions", []), "gap_probing")

        if not tq and not bq and not gq:
            rule_qb = _rule_based_question_bank(resume, job, gap_report, req)
            tq, bq, gq = rule_qb.technical_questions, rule_qb.behavioral_questions, rule_qb.gap_questions

        tips = data.get("preparation_tips", [])
        if not isinstance(tips, list) or not tips:
            tips = [
                f"Research {job.company_name or 'the company'} before the interview.",
                "Prepare STAR stories for key technical challenges.",
                "Review foundational concepts in your target skills."
            ]

        return QuestionBank(
            resume_id=str(resume.id),
            job_id=str(job.id),
            job_title=gap_report.job_title,
            candidate_name=candidate_name,
            technical_questions=tq,
            behavioral_questions=bq,
            gap_questions=gq,
            preparation_tips=[str(t) for t in tips],
        )

    _gemini_question_bank = _ollama_question_bank

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

    async def _ollama_evaluate_answer(self, req: AnswerEvaluationRequest) -> AnswerEvaluationResponse:
        prompt = self._build_evaluation_prompt(req)
        data = await self._ollama_post(prompt, num_predict=350)
        grade = str(data.get("grade", "needs_improvement")).lower().strip()
        if grade not in ("excellent", "good", "needs_improvement", "poor"):
            grade = "needs_improvement"

        score = data.get("score", 5.0)
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = 5.0

        rubric = data.get("rubric_breakdown", {})
        if not isinstance(rubric, dict):
            rubric = {"technical_accuracy": 5.0, "depth": 5.0, "structure": 5.0, "specificity": 5.0}
        else:
            clean_rubric = {}
            for k, v in rubric.items():
                try:
                    clean_rubric[str(k)] = float(v)
                except (ValueError, TypeError):
                    clean_rubric[str(k)] = 5.0
            rubric = clean_rubric

        strengths = data.get("strengths", [])
        if not isinstance(strengths, list):
            strengths = [str(strengths)] if strengths else []

        weaknesses = data.get("weaknesses", [])
        if not isinstance(weaknesses, list):
            weaknesses = [str(weaknesses)] if weaknesses else []

        return AnswerEvaluationResponse(
            score=score,
            grade=grade,  # type: ignore[arg-type]
            strengths=[str(s) for s in strengths],
            weaknesses=[str(w) for w in weaknesses],
            improved_answer=str(data.get("improved_answer", "")),
            rubric_breakdown=rubric,
        )

    _gemini_evaluate_answer = _ollama_evaluate_answer


# Module-level singleton
coach_agent = CoachAgent()
coach_service = coach_agent
