"""Market Intelligence Agent Service - Sprint 6.

Aggregates job market trends, salary benchmarks, skill demand signals,
and location heat-maps from the existing job_postings table.

Uses Gemini as the primary LLM for narrative generation, with a
high-fidelity deterministic rule-based fallback so all tests pass
without network access.
"""

import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import select, func, text, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.services.matcher_service import FeatureExtractor
from app.schemas.market import (
    DemandHeatmapRequest,
    DemandHeatmapResponse,
    LocationDemandItem,
    ResumePositioningRequest,
    ResumePositioningResponse,
    RoleOverviewRequest,
    RoleOverviewResponse,
    SalaryBand,
    SalaryInsightsRequest,
    SalaryInsightsResponse,
    SkillAlignmentItem,
    SkillDemandItem,
    SkillDemandRequest,
    SkillDemandResponse,
    TopPayingCompany,
    WorkTypeBreakdown,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

from app.core.taxonomy import LINKEDIN_CATEGORY_CODES as _CATEGORY_CODES

# Hours per year for HOURLY → YEARLY conversion
_HOURS_PER_YEAR: float = 2080.0

# Minimum sample size to trust salary statistics
_MIN_SALARY_SAMPLE: int = 3


# ---------------------------------------------------------------------------
# Pure helpers — tested without DB or LLM
# ---------------------------------------------------------------------------

def normalise_salary(value: Optional[float], pay_period: Optional[str]) -> Optional[float]:
    """Convert any pay-period salary to an annual equivalent."""
    if value is None or value <= 0:
        return None
    period = (pay_period or "YEARLY").upper()
    if period == "HOURLY":
        return round(value * _HOURS_PER_YEAR, 2)
    if period == "WEEKLY":
        return round(value * 52, 2)
    if period == "MONTHLY":
        return round(value * 12, 2)
    # YEARLY or unknown — return as-is
    return round(value, 2)


def _percentile(sorted_values: List[float], pct: float) -> Optional[float]:
    """Return the pct-th percentile (0–100) from a sorted list."""
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct / 100.0
    lo = int(k)
    hi = lo + 1
    if hi >= len(sorted_values):
        return round(sorted_values[-1], 2)
    frac = k - lo
    return round(sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo]), 2)


def aggregate_salary(rows: List[Dict[str, Any]]) -> SalaryBand:
    """Aggregate salary rows into a SalaryBand. All inputs normalised to annual."""
    annual_values: List[float] = []
    for row in rows:
        pay_period = row.get("pay_period")
        for col in ("med_salary", "min_salary", "max_salary"):
            val = normalise_salary(row.get(col), pay_period)
            if val is not None and 5_000 <= val <= 2_000_000:  # sanity bounds
                annual_values.append(val)

    if not annual_values:
        return SalaryBand(sample_size=0)

    annual_values.sort()
    return SalaryBand(
        min_annual=round(annual_values[0], 2),
        p25_annual=_percentile(annual_values, 25),
        median_annual=_percentile(annual_values, 50),
        p75_annual=_percentile(annual_values, 75),
        max_annual=round(annual_values[-1], 2),
        mean_annual=round(sum(annual_values) / len(annual_values), 2),
        currency="USD",
        sample_size=len(annual_values),
    )


def compute_skill_demand(
    skills_arrays: List[List[str]],
    total_postings: int,
    top_n: int = 10,
) -> List[SkillDemandItem]:
    """Count skill frequencies across job postings, filtering category codes."""
    counter: Counter = Counter()
    for arr in skills_arrays:
        seen_in_posting = set()
        for skill in arr:
            if isinstance(skill, str) and skill.strip():
                clean = skill.strip()
                if clean.upper() not in _CATEGORY_CODES and len(clean) > 1:
                    clean_lower = clean.lower()
                    if clean_lower not in seen_in_posting:
                        seen_in_posting.add(clean_lower)
                        counter[clean] += 1

    result: List[SkillDemandItem] = []
    for skill, count in counter.most_common(top_n):
        pct = round(count / max(total_postings, 1) * 100, 1)
        if pct >= 20:
            signal = "high"
        elif pct >= 8:
            signal = "moderate"
        else:
            signal = "low"
        result.append(SkillDemandItem(
            skill=skill,
            posting_count=count,
            percentage=pct,
            trend_signal=signal,
        ))
    return result


def _classify_work_type(work_type: Optional[str]) -> str:
    if not work_type:
        return "other"
    wt = work_type.upper()
    if "FULL" in wt:
        return "full_time"
    if "PART" in wt:
        return "part_time"
    if "CONTRACT" in wt or "CONTRACTOR" in wt:
        return "contract"
    if "INTERN" in wt:
        return "internship"
    return "other"


# ---------------------------------------------------------------------------
# Rule-based narrative generators
# ---------------------------------------------------------------------------

def _rule_based_salary_narrative(
    role: str,
    band: SalaryBand,
    location: Optional[str],
) -> str:
    if band.sample_size < _MIN_SALARY_SAMPLE:
        return (
            f"Salary data for {role!r} roles is limited in the current dataset "
            f"(fewer than {_MIN_SALARY_SAMPLE} records with salary information). "
            f"For the most accurate benchmarks, consult LinkedIn Salary Insights, "
            f"Glassdoor, or Levels.fyi."
        )
    loc_str = f" in {location}" if location else ""
    median = f"${band.median_annual:,.0f}" if band.median_annual else "N/A"
    low = f"${band.p25_annual:,.0f}" if band.p25_annual else "N/A"
    high = f"${band.p75_annual:,.0f}" if band.p75_annual else "N/A"
    return (
        f"Based on {band.sample_size} salary data points from current job postings, "
        f"{role!r} roles{loc_str} offer a median annual salary of {median}. "
        f"The middle 50% of positions pay between {low} and {high} per year. "
        f"Candidates with in-demand skills such as cloud platforms, modern frameworks, "
        f"and strong communication are positioned to negotiate toward the upper quartile."
    )


def _rule_based_skills_narrative(
    role_context: str,
    skills: List[SkillDemandItem],
    total: int,
) -> str:
    if not skills:
        return (
            f"No specific skill data found for {role_context!r}. "
            f"Broaden your search or check back as more postings are indexed."
        )
    top3 = ", ".join(s.skill for s in skills[:3])
    high_demand = [s.skill for s in skills if s.trend_signal == "high"]
    hd_str = ", ".join(high_demand[:4]) if high_demand else top3
    return (
        f"Across {total} {role_context!r} postings analysed, the top skills are "
        f"{top3}. High-demand skills (mentioned in 20%+ of postings) include: "
        f"{hd_str}. Candidates who demonstrate these competencies will stand out "
        f"in screening and skills-based assessments."
    )


def _rule_based_heatmap_narrative(
    role_context: str,
    locations: List[LocationDemandItem],
    total: int,
) -> str:
    if not locations:
        return f"No location data found for {role_context!r} postings."
    hottest = locations[0]
    remote_heavy = [l for l in locations if l.remote_pct >= 50]
    remote_str = (
        f" {len(remote_heavy)} location(s) show 50%+ remote postings, "
        f"indicating strong remote-work flexibility."
        if remote_heavy else ""
    )
    return (
        f"Across {total} postings, {hottest.location!r} leads with "
        f"{hottest.posting_count} {role_context!r} openings "
        f"({hottest.percentage:.1f}% of total).{remote_str} "
        f"Candidates open to relocation or remote work should target these markets first."
    )


def _rule_based_overview_narrative(
    title: str,
    total: int,
    remote_pct: float,
    band: SalaryBand,
    top_skills: List[SkillDemandItem],
) -> str:
    remote_str = f"{remote_pct:.0f}% of postings allow remote work. " if remote_pct > 0 else ""
    median = f"${band.median_annual:,.0f}/yr" if band.median_annual else "data unavailable"
    top3 = ", ".join(s.skill for s in top_skills[:3]) if top_skills else "varied skills"
    return (
        f"The {title!r} market currently shows {total} active postings. "
        f"{remote_str}"
        f"Median annual compensation is {median}. "
        f"The most sought-after skills are {top3}. "
        f"Candidates should tailor their resume and portfolio to highlight these competencies "
        f"for maximum visibility in applicant tracking systems."
    )


def _rule_based_positioning_narrative(
    candidate_name: Optional[str],
    coverage_pct: float,
    matched: int,
    total_skills: int,
    band: SalaryBand,
    gaps: List[SkillAlignmentItem],
) -> Tuple[str, List[str]]:
    name = candidate_name or "The candidate"
    gap_names = [g.skill for g in gaps[:3] if not g.candidate_has]
    gap_str = ", ".join(gap_names) if gap_names else "none identified"
    median = f"${band.median_annual:,.0f}/yr" if band.median_annual else "N/A"

    narrative = (
        f"{name} matches {matched} of the top {total_skills} market skills, "
        f"covering {coverage_pct:.0f}% of current market demand. "
        f"The median salary for roles aligned with this profile is {median}. "
        f"Key skills to add for stronger market positioning: {gap_str}."
    )
    tips: List[str] = [
        "Tailor your resume headline to include the top 2-3 in-demand skill keywords.",
        "Add quantified project outcomes (e.g., '60% latency reduction') to strengthen ATS ranking.",
        f"Prioritise learning: {gap_str} — these appear in the most postings for your target role.",
        "Target locations and companies with the highest posting activity for faster job-search ROI.",
        "Consider remote-first roles to expand your geographic reach significantly.",
    ]
    return narrative, tips


# ---------------------------------------------------------------------------
# MarketAgent
# ---------------------------------------------------------------------------

class MarketAgent:
    """Market Intelligence Agent — query-driven insights from job_postings."""

    def __init__(self) -> None:
        self.gemini_key: Optional[str] = settings.GEMINI_API_KEY
        self.gemini_model: str = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def get_salary_insights(
        self,
        db: AsyncSession,
        req: Optional[SalaryInsightsRequest] = None,
        *,
        title_query: Optional[str] = None,
        location: Optional[str] = None,
        pay_period_filter: Optional[str] = "ALL",
    ) -> SalaryInsightsResponse:
        if req is None:
            req = SalaryInsightsRequest(
                title_query=title_query or "",
                location=location,
                pay_period_filter=pay_period_filter,  # type: ignore[arg-type]
            )
        rows, companies = await self._query_salary_rows(db, req.title_query, req.location)
        band = aggregate_salary(rows)

        if band.sample_size < _MIN_SALARY_SAMPLE:
            quality_note = (
                f"Only {band.sample_size} salary record(s) found. "
                f"Results may not be statistically representative. "
                f"Try broadening your title query or removing the location filter."
            )
        else:
            quality_note = f"Based on {band.sample_size} salary data points."

        narrative = await self._gemini_narrative(
            mode="salary",
            data={"role": req.title_query, "band": band.model_dump(), "location": req.location},
        )
        if not narrative:
            narrative = _rule_based_salary_narrative(req.title_query, band, req.location)

        return SalaryInsightsResponse(
            role_title=req.title_query,
            location_filter=req.location,
            salary_band=band,
            top_paying_companies=companies[:5],
            narrative=narrative,
            data_quality_note=quality_note,
        )

    async def get_trending_skills(
        self,
        db: AsyncSession,
        req: Optional[SkillDemandRequest] = None,
        *,
        title_query: Optional[str] = None,
        location: Optional[str] = None,
        top_n: int = 10,
    ) -> SkillDemandResponse:
        if req is None:
            req = SkillDemandRequest(
                title_query=title_query,
                location=location,
                top_n=top_n,
            )
        skills_arrays, total = await self._query_skills_arrays(
            db, req.title_query, req.location
        )
        items = compute_skill_demand(skills_arrays, total, req.top_n)
        role_context = req.title_query or "all roles"

        narrative = await self._gemini_narrative(
            mode="skills",
            data={
                "role": role_context,
                "total": total,
                "top_skills": [s.model_dump() for s in items[:10]],
            },
        )
        if not narrative:
            narrative = _rule_based_skills_narrative(role_context, items, total)

        return SkillDemandResponse(
            role_context=role_context,
            total_postings_analysed=total,
            skills=items,
            narrative=narrative,
        )

    async def get_demand_heatmap(
        self, db: AsyncSession, req: DemandHeatmapRequest
    ) -> DemandHeatmapResponse:
        locations, total = await self._query_location_demand(
            db, req.title_query, req.top_n
        )
        role_context = req.title_query or "all roles"
        hottest = locations[0].location if locations else None

        narrative = await self._gemini_narrative(
            mode="heatmap",
            data={
                "role": role_context,
                "total": total,
                "top_locations": [l.model_dump() for l in locations[:5]],
            },
        )
        if not narrative:
            narrative = _rule_based_heatmap_narrative(role_context, locations, total)

        return DemandHeatmapResponse(
            role_context=role_context,
            total_postings_analysed=total,
            locations=locations,
            hottest_market=hottest,
            narrative=narrative,
        )

    async def get_role_overview(
        self, db: AsyncSession, req: RoleOverviewRequest
    ) -> RoleOverviewResponse:
        # Salary
        salary_rows, companies = await self._query_salary_rows(db, req.title_query, req.location)
        band = aggregate_salary(salary_rows)

        # Skills
        skills_arrays, total = await self._query_skills_arrays(db, req.title_query, req.location)
        top_skills = compute_skill_demand(skills_arrays, total, top_n=8)

        # Locations
        locations, _ = await self._query_location_demand(db, req.title_query, top_n=5)

        # Work type + remote breakdown
        work_breakdown, remote_pct = await self._query_work_type_breakdown(
            db, req.title_query, req.location
        )

        top_companies = [c.company_name for c in companies[:5]]

        quality_note = (
            f"Based on {total} postings with {band.sample_size} salary record(s)."
        )

        narrative = await self._gemini_narrative(
            mode="overview",
            data={
                "role": req.title_query,
                "total": total,
                "remote_pct": remote_pct,
                "band": band.model_dump(),
                "top_skills": [s.model_dump() for s in top_skills[:5]],
                "top_companies": top_companies,
            },
        )
        if not narrative:
            narrative = _rule_based_overview_narrative(
                req.title_query, total, remote_pct, band, top_skills
            )

        return RoleOverviewResponse(
            title_query=req.title_query,
            location_filter=req.location,
            total_postings=total,
            work_type_breakdown=work_breakdown,
            remote_pct=remote_pct,
            top_companies=top_companies,
            salary_band=band,
            top_skills=top_skills,
            top_locations=locations,
            narrative=narrative,
            data_quality_note=quality_note,
        )

    async def get_resume_positioning(
        self, db: AsyncSession, resume: Resume
    ) -> ResumePositioningResponse:
        pd = resume.parsed_data or {}
        candidate_skills: List[str] = [
            s for s in pd.get("skills", [])
            if isinstance(s, str) and s.upper() not in _CATEGORY_CODES and len(s) > 1
        ]
        # Also pull from projects
        for proj in pd.get("projects", []):
            for tech in proj.get("technologies", []):
                if isinstance(tech, str) and tech.upper() not in _CATEGORY_CODES:
                    if tech not in candidate_skills:
                        candidate_skills.append(tech)

        # Use skills as the title query — pick first recognisable tech skill
        title_query = None
        edu = pd.get("education", [])
        for e in edu:
            fos = str(e.get("field_of_study", "")).lower()
            if any(w in fos for w in ["computer", "software", "data", "ai", "intelligence"]):
                title_query = "Software Engineer"
                break
        if not title_query and candidate_skills:
            title_query = candidate_skills[0]

        # Market skill demand for matched roles
        skills_arrays, total = await self._query_skills_arrays(db, title_query, None)
        top_market = compute_skill_demand(skills_arrays, total, top_n=20)

        # Build skill alignment
        candidate_set = {s.lower() for s in candidate_skills}
        alignment: List[SkillAlignmentItem] = []
        matched = 0
        for item in top_market:
            has = item.skill.lower() in candidate_set
            if has:
                matched += 1
                signal: str = "strength"
            elif item.trend_signal == "high":
                signal = "gap"
            else:
                signal = "opportunity"
            alignment.append(SkillAlignmentItem(
                skill=item.skill,
                market_demand_pct=item.percentage,
                candidate_has=has,
                signal=signal,  # type: ignore[arg-type]
            ))

        coverage_pct = round(matched / max(len(top_market), 1) * 100, 1)

        # Salary band for relevant roles
        salary_rows, _ = await self._query_salary_rows(db, title_query, None)
        band = aggregate_salary(salary_rows)

        # Top locations
        locations, _ = await self._query_location_demand(db, title_query, top_n=5)
        competitive_locations = [l.location for l in locations]

        gaps = [a for a in alignment if not a.candidate_has]
        narrative, tips = _rule_based_positioning_narrative(
            resume.candidate_name, coverage_pct, matched, len(top_market), band, gaps
        )

        gemini_narrative = await self._gemini_narrative(
            mode="positioning",
            data={
                "candidate": resume.candidate_name,
                "coverage_pct": coverage_pct,
                "matched": matched,
                "total_skills": len(top_market),
                "band": band.model_dump(),
                "gaps": [g.skill for g in gaps[:5]],
                "strengths": [a.skill for a in alignment if a.candidate_has][:5],
            },
        )
        if gemini_narrative:
            narrative = gemini_narrative

        return ResumePositioningResponse(
            resume_id=str(resume.id),
            candidate_name=resume.candidate_name,
            total_relevant_postings=total,
            skill_alignment=alignment,
            matched_skill_count=matched,
            coverage_pct=coverage_pct,
            salary_expectation_band=band,
            competitive_locations=competitive_locations,
            market_narrative=narrative,
            positioning_tips=tips,
        )

    # -----------------------------------------------------------------------
    # DB query helpers
    # -----------------------------------------------------------------------

    async def _query_salary_rows(
        self,
        db: AsyncSession,
        title_query: Optional[str],
        location: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], List[TopPayingCompany]]:
        """Fetch salary-related columns from job_postings."""
        stmt = select(
            JobPosting.min_salary,
            JobPosting.max_salary,
            JobPosting.med_salary,
            JobPosting.pay_period,
            JobPosting.company_name,
        )
        if title_query:
            stmt = stmt.where(JobPosting.title.ilike(f"%{title_query}%"))
        if location:
            stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))

        result = await db.execute(stmt)
        raw = result.fetchall()

        rows: List[Dict[str, Any]] = [
            {
                "min_salary": r.min_salary,
                "max_salary": r.max_salary,
                "med_salary": r.med_salary,
                "pay_period": r.pay_period,
                "company_name": r.company_name,
            }
            for r in raw
        ]

        # Top paying companies — group by company, compute median
        company_salaries: Dict[str, List[float]] = defaultdict(list)
        for row in rows:
            company = row.get("company_name") or "Unknown"
            val = normalise_salary(row.get("med_salary") or row.get("min_salary"), row.get("pay_period"))
            if val:
                company_salaries[company].append(val)

        companies: List[TopPayingCompany] = sorted(
            [
                TopPayingCompany(
                    company_name=name,
                    median_salary=round(sorted(vals)[len(vals) // 2], 2),
                    posting_count=len(vals),
                )
                for name, vals in company_salaries.items()
                if vals
            ],
            key=lambda c: c.median_salary or 0,
            reverse=True,
        )

        return rows, companies

    async def _query_skills_arrays(
        self,
        db: AsyncSession,
        title_query: Optional[str],
        location: Optional[str],
    ) -> Tuple[List[List[str]], int]:
        """Fetch and extract genuine skills from matching job_postings."""
        stmt = select(JobPosting.skills, JobPosting.title, JobPosting.description)
        if title_query:
            stmt = stmt.where(JobPosting.title.ilike(f"%{title_query}%"))
        if location:
            stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))

        result = await db.execute(stmt)
        raw = result.fetchall()

        arrays: List[List[str]] = []
        for r in raw:
            skills_val = r.skills
            raw_skills: List[str] = []
            if isinstance(skills_val, list):
                raw_skills = skills_val
            elif isinstance(skills_val, str):
                try:
                    parsed = json.loads(skills_val)
                    if isinstance(parsed, list):
                        raw_skills = parsed
                except Exception:
                    pass

            extracted = FeatureExtractor.extract_job_skills(
                description=r.description or "",
                title=r.title or "",
                raw_job_skills=raw_skills,
            )
            arrays.append(extracted)

        return arrays, len(raw)

    async def _query_location_demand(
        self,
        db: AsyncSession,
        title_query: Optional[str],
        top_n: int,
    ) -> Tuple[List[LocationDemandItem], int]:
        """GROUP BY location, count postings and compute avg salary + remote pct."""
        stmt = select(
            JobPosting.location,
            func.count(JobPosting.id).label("cnt"),
            func.avg(
                func.coalesce(JobPosting.med_salary, JobPosting.min_salary)
            ).label("avg_sal"),
            func.avg(
                case((JobPosting.remote_allowed.is_(True), 1.0), else_=0.0)
            ).label("remote_avg"),
        ).group_by(JobPosting.location).order_by(func.count(JobPosting.id).desc())

        if title_query:
            stmt = stmt.where(JobPosting.title.ilike(f"%{title_query}%"))

        result = await db.execute(stmt)
        raw = result.fetchall()

        total = sum(r.cnt for r in raw if r.location)
        items: List[LocationDemandItem] = []
        for r in raw:
            if not r.location:
                continue
            avg_sal: Optional[float] = None
            if r.avg_sal is not None:
                avg_sal = normalise_salary(float(r.avg_sal), "YEARLY")
            remote_pct = round(float(r.remote_avg or 0) * 100, 1)
            pct = round(r.cnt / max(total, 1) * 100, 1)
            items.append(LocationDemandItem(
                location=r.location,
                posting_count=r.cnt,
                percentage=pct,
                avg_annual_salary=avg_sal,
                remote_pct=remote_pct,
            ))
            if len(items) >= top_n:
                break

        return items, total

    async def _query_work_type_breakdown(
        self,
        db: AsyncSession,
        title_query: Optional[str],
        location: Optional[str],
    ) -> Tuple[WorkTypeBreakdown, float]:
        """Returns WorkTypeBreakdown + overall remote percentage."""
        stmt = select(JobPosting.work_type, JobPosting.remote_allowed)
        if title_query:
            stmt = stmt.where(JobPosting.title.ilike(f"%{title_query}%"))
        if location:
            stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))

        result = await db.execute(stmt)
        raw = result.fetchall()

        breakdown = WorkTypeBreakdown()
        remote_count = 0
        for r in raw:
            cat = _classify_work_type(r.work_type)
            setattr(breakdown, cat, getattr(breakdown, cat) + 1)
            if r.remote_allowed:
                remote_count += 1

        total = len(raw)
        remote_pct = round(remote_count / max(total, 1) * 100, 1)
        return breakdown, remote_pct

    # -----------------------------------------------------------------------
    # Gemini narrative generator
    # -----------------------------------------------------------------------

    async def _gemini_narrative(self, mode: str, data: Dict[str, Any]) -> str:
        """Generate a market narrative via Gemini. Returns '' on any failure."""
        if not self.gemini_key:
            return ""

        instruction = (
            "Requirements:\n"
            "- Write in clear, professional, plain prose paragraphs (no markdown headings, bold labels, bullet points, or lists).\n"
            "- Do NOT output any internal drafting thoughts, outlines, preambles, or labels such as 'Drafting:', 'Notes:', or 'Analysis:'.\n"
            "- Begin directly with the first sentence of the insight."
        )

        prompts = {
            "salary": (
                "You are a professional labor market analyst. Write a concise, cohesive 2-paragraph salary "
                "market insight for job seekers and hiring managers based on this data:\n"
                f"{json.dumps(data, indent=2)}\n\n"
                f"{instruction}"
            ),
            "skills": (
                "You are a tech talent analyst. Write a concise, cohesive 2-paragraph skill-demand "
                "insight based on this data:\n"
                f"{json.dumps(data, indent=2)}\n\n"
                f"{instruction}"
            ),
            "heatmap": (
                "You are a job market geographer. Write a concise, cohesive 2-paragraph location "
                "demand insight based on this data:\n"
                f"{json.dumps(data, indent=2)}\n\n"
                f"{instruction}"
            ),
            "overview": (
                "You are a senior career advisor. Write a concise, cohesive 3-paragraph market overview "
                "for a job seeker based on this role data:\n"
                f"{json.dumps(data, indent=2)}\n\n"
                f"{instruction}"
            ),
            "positioning": (
                "You are a career coach specialising in market positioning. Write a concise, cohesive 2-paragraph "
                "personalised market positioning narrative for this candidate:\n"
                f"{json.dumps(data, indent=2)}\n\n"
                f"{instruction}"
            ),
        }
        prompt = prompts.get(mode, f"Summarise this job market data:\n{json.dumps(data)}\n\n{instruction}")

        try:
            model_name = self.gemini_model.removeprefix("models/")
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={self.gemini_key}"
            )
            payload: Dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 2048,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                # Fallback if the specific model variant rejects thinkingConfig
                if resp.status_code == 400 and "thinkingConfig" in resp.text:
                    payload["generationConfig"] = {"maxOutputTokens": 2048}
                    resp = await client.post(url, json=payload)

                resp.raise_for_status()
                data_resp = resp.json()

                candidates = data_resp.get("candidates", [])
                if not candidates:
                    return ""

                candidate = candidates[0]
                finish_reason = candidate.get("finishReason")
                parts = candidate.get("content", {}).get("parts", [])

                # Extract text parts only (skipping any explicit thought parts)
                text_parts = [
                    p.get("text", "")
                    for p in parts
                    if not p.get("thought") and isinstance(p.get("text"), str)
                ]
                raw_text = "".join(text_parts).strip()

                if finish_reason == "MAX_TOKENS" and len(raw_text.split()) < 30:
                    logger.warning(
                        f"Gemini narrative ({mode}) was truncated (MAX_TOKENS with only {len(raw_text.split())} words); using fallback."
                    )
                    return ""

                # Clean any accidental drafting/outline artifacts
                cleaned_lines = []
                for line in raw_text.splitlines():
                    stripped = line.strip()
                    if re.match(
                        r"^(?:\*?\s*(?:Drafting|Draft|Analysis|Notes|Outline):|\*\*[^*]+\*\*:?)\s*$",
                        stripped,
                        re.IGNORECASE,
                    ):
                        continue
                    line = re.sub(
                        r"^(?:\*?\s*(?:Drafting|Draft|Analysis|Notes):)\s*",
                        "",
                        line,
                        flags=re.IGNORECASE,
                    )
                    cleaned_lines.append(line)

                final_text = "\n".join(cleaned_lines).strip()

                # If text is too short to be a valid multi-paragraph narrative, reject and fall back
                if len(final_text.split()) < 25:
                    logger.warning(
                        f"Gemini narrative ({mode}) too short ({len(final_text.split())} words); using rule-based fallback."
                    )
                    return ""

                return final_text
        except Exception as exc:
            logger.warning(f"MarketAgent Gemini narrative failed ({mode}): {exc}")
            return ""


# Module-level singleton
market_agent = MarketAgent()
market_service = market_agent
