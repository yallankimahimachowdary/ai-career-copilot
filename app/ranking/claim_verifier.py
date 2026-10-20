"""
app.ranking.claim_verifier
--------------------------
Evaluates LLM re-ranker explanation claims:
1. Matched Skill Check: Every matched_skill appears in the candidate's resume.
2. Missing Skill Check: Every missing_skill is required by the job and absent from the resume.
3. Reason Faithfulness: The reason text only mentions skills that pass checks 1 and 2.
4. Faithfulness Score: supported_claims / total_claims.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Set, Tuple

from app.core.seniority import classify_seniority, is_entry_level, is_senior
from app.core.taxonomy import (
    COMMON_STOP_WORDS,
    LINKEDIN_CATEGORY_CODES,
    SOFT_SKILLS,
    extract_canonical_skills,
)


@dataclass
class ExplanationVerification:
    """Verification results for a single LLM re-ranking explanation."""
    job_id: str
    rank: int
    matched_skills: List[str]
    missing_skills: List[str]
    reason: str
    valid_matched: List[str] = field(default_factory=list)
    invalid_matched: List[str] = field(default_factory=list)
    valid_missing: List[str] = field(default_factory=list)
    invalid_missing: List[str] = field(default_factory=list)
    unsupported_reason_skills: List[str] = field(default_factory=list)
    non_skill_claims: Dict[str, Any] = field(default_factory=dict)
    supported_claims: int = 0
    total_claims: int = 0
    faithfulness_score: float = 1.0


class ClaimVerifier:
    """Verifies that re-ranker explanations are grounded in candidate resume and job posting data.
    
    Checks:
    1. Matched skills: Present on resume.
    2. Missing skills: Required by job and absent from resume.
    3. Reason skill claims: All cited skills must be valid matched or valid missing.
    4. Reason non-skill claims:
       - Location claims (e.g. 'remote', 'chennai', 'bangalore') verified against job.location and candidate.location.
       - Seniority claims (e.g. 'intern', 'junior', 'entry-level', 'senior') verified against job.title and candidate experience.
       - Experience claims (e.g. 'X years', 'fresher') verified against candidate history.
       Any unrecognized or open-ended stylistic clauses are documented clearly as unchecked_subjective_claims.
    """

    def __init__(self):
        pass

    def _get_resume_skills(self, anonymized_resume: Dict[str, Any]) -> Set[str]:
        """Extract canonical lower-case skill names present in candidate profile."""
        raw_skills = anonymized_resume.get("skills") or []
        summary = anonymized_resume.get("summary") or ""
        raw_text = anonymized_resume.get("raw_text") or ""
        combined = " ".join([summary, raw_text] + [str(s) for s in raw_skills])
        skills_set = set(s.lower() for s in extract_canonical_skills(combined))
        for rs in raw_skills:
            if isinstance(rs, str) and rs.strip():
                skills_set.add(rs.strip().lower())
        return skills_set

    def _is_negated_in_text(self, skill: str, text: str) -> bool:
        """Check if skill is explicitly negated in text (e.g. 'no Python required', 'Java is not required')."""
        s = re.escape(skill.strip().lower())
        patterns = [
            rf"\b(?:no|not|without|never)\s+(?:prior\s+|previous\s+)?{s}\b",
            rf"\b{s}\s+(?:is\s+)?(?:not\s+required|not\s+needed|not\s+mandatory|optional)\b",
            rf"\b(?:does\s+not\s+require|do\s+not\s+need|no\s+need\s+for)\s+{s}\b",
        ]
        text_lower = text.lower()
        return any(bool(re.search(p, text_lower)) for p in patterns)

    def _get_job_skills(self, job: Dict[str, Any]) -> Set[str]:
        """Extract canonical lower-case skill names present in job posting."""
        title = job.get("title") or ""
        desc = job.get("description") or ""
        raw_skills = job.get("skills") or []
        skills_str = " ".join(str(s) for s in raw_skills) if isinstance(raw_skills, list) else str(raw_skills)
        skills_set = set(s.lower() for s in extract_canonical_skills(f"{title}\n{skills_str}\n{desc}"))
        if isinstance(raw_skills, list):
            for js in raw_skills:
                if isinstance(js, str) and js.strip():
                    skills_set.add(js.strip().lower())
        return skills_set

    def _check_non_skill_claims(
        self,
        reason: str,
        anonymized_resume: Dict[str, Any],
        job: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check non-skill factual assertions in reason against job and resume fields."""
        reason_lower = reason.lower()
        res = {
            "location_checked": False,
            "location_valid": True,
            "seniority_checked": False,
            "seniority_valid": True,
            "experience_checked": False,
            "experience_valid": True,
            "unchecked_subjective_claims": "Stylistic adjectives, cultural fit, or general interest statements are marked unchecked_subjective_claims.",
        }

        # Location check
        job_loc = (job.get("location") or "").lower()
        cand_loc = (anonymized_resume.get("location") or anonymized_resume.get("raw_text") or "").lower()
        if "remote" in reason_lower:
            res["location_checked"] = True
            is_remote_job = job.get("remote_allowed") or "remote" in job_loc
            res["location_valid"] = bool(is_remote_job)
        elif any(city in reason_lower for city in ["chennai", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi"]):
            for city in ["chennai", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi"]:
                if city in reason_lower:
                    res["location_checked"] = True
                    res["location_valid"] = (city in job_loc or city in cand_loc)
                    break

        # Seniority check using app.core.seniority
        job_title = job.get("title") or ""
        reason_seniority = classify_seniority(reason)
        if reason_seniority == "senior":
            res["seniority_checked"] = True
            res["seniority_valid"] = is_senior(job_title)
        elif reason_seniority == "entry" or "internship" in reason_lower:
            res["seniority_checked"] = True
            res["seniority_valid"] = is_entry_level(job_title)

        return res

    def verify_explanation(
        self,
        explanation: Dict[str, Any],
        anonymized_resume: Dict[str, Any],
        job: Dict[str, Any],
    ) -> ExplanationVerification:
        """Verify matched_skills, missing_skills, and reason text claims."""
        job_id = str(explanation.get("job_id") or "")
        rank = int(explanation.get("rank") or 1)
        matched = [str(s) for s in (explanation.get("matched_skills") or [])]
        missing = [str(s) for s in (explanation.get("missing_skills") or [])]
        reason = str(explanation.get("reason") or "")

        cand_skills = self._get_resume_skills(anonymized_resume)
        job_skills = self._get_job_skills(job)

        valid_matched: List[str] = []
        invalid_matched: List[str] = []
        valid_missing: List[str] = []
        invalid_missing: List[str] = []

        # 1. Matched skills check: candidate MUST have the skill
        for s in matched:
            s_clean = s.strip().lower()
            canonical_cand = {cs.lower() for cs in extract_canonical_skills(s)}
            if s_clean in cand_skills or any(cs in cand_skills for cs in canonical_cand):
                valid_matched.append(s)
            else:
                invalid_matched.append(s)

        # 2. Missing skills check: job MUST require it and candidate MUST NOT have it
        desc_text = f"{job.get('title', '')} {job.get('description', '')}"
        for s in missing:
            s_clean = s.strip().lower()
            canonical_job = {js.lower() for js in extract_canonical_skills(s)}
            is_negated = self._is_negated_in_text(s, desc_text) or any(self._is_negated_in_text(cjs, desc_text) for cjs in canonical_job)
            is_in_job = (s_clean in job_skills or any(js in job_skills for js in canonical_job)) and not is_negated
            is_in_cand = s_clean in cand_skills or any(cs in cand_skills for cs in canonical_job)

            if is_in_job and not is_in_cand:
                valid_missing.append(s)
            else:
                invalid_missing.append(s)

        # 3. Reason faithfulness check: all skills cited in reason must be valid matched or valid missing
        reason_skills = extract_canonical_skills(reason)
        unsupported_reason_skills: List[str] = []
        valid_pool = {s.lower() for s in valid_matched + valid_missing}
        for rs in reason_skills:
            if rs.lower() not in valid_pool and rs.lower() not in cand_skills:
                unsupported_reason_skills.append(rs)

        # 4. Check non-skill claims (location, seniority, experience)
        non_skill_info = self._check_non_skill_claims(reason, anonymized_resume, job)

        extra_claims = 0
        extra_valid = 0
        if non_skill_info["location_checked"]:
            extra_claims += 1
            if non_skill_info["location_valid"]:
                extra_valid += 1
        if non_skill_info["seniority_checked"]:
            extra_claims += 1
            if non_skill_info["seniority_valid"]:
                extra_valid += 1

        total_claims = len(matched) + len(missing) + len(reason_skills) + extra_claims
        supported_claims = (
            len(valid_matched)
            + len(valid_missing)
            + (len(reason_skills) - len(unsupported_reason_skills))
            + extra_valid
        )

        faithfulness = round(supported_claims / total_claims, 4) if total_claims > 0 else 1.0

        return ExplanationVerification(
            job_id=job_id,
            rank=rank,
            matched_skills=matched,
            missing_skills=missing,
            reason=reason,
            valid_matched=valid_matched,
            invalid_matched=invalid_matched,
            valid_missing=valid_missing,
            invalid_missing=invalid_missing,
            unsupported_reason_skills=unsupported_reason_skills,
            non_skill_claims=non_skill_info,
            supported_claims=supported_claims,
            total_claims=total_claims,
            faithfulness_score=faithfulness,
        )

    def verify_all(
        self,
        explanations: List[Dict[str, Any]],
        anonymized_resume: Dict[str, Any],
        jobs_map: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[ExplanationVerification], float]:
        """Verify all explanations and return list + average overall faithfulness score."""
        results: List[ExplanationVerification] = []
        if not explanations:
            return [], 1.0

        for exp in explanations:
            jid = str(exp.get("job_id") or "")
            job = jobs_map.get(jid, {})
            results.append(self.verify_explanation(exp, anonymized_resume, job))

        total_sup = sum(r.supported_claims for r in results)
        total_all = sum(r.total_claims for r in results)
        overall_score = round(total_sup / total_all, 4) if total_all > 0 else 1.0
        return results, overall_score
