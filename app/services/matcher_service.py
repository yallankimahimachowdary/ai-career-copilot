import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.matcher import (
    CandidateMatchItem,
    FeatureBreakdown,
    JobCandidatesMatchResponse,
    JobMatchItem,
    MatchCompareResponse,
    ResumeMatchResponse,
    ShapExplanation,
    SkillsBreakdown,
)
from app.services.embedding_service import embedding_service


from app.core.taxonomy import LINKEDIN_CATEGORY_CODES


# ------------------------------------------------------------------------------
# Feature Extractor
# ------------------------------------------------------------------------------
class FeatureExtractor:
    """Extracts granular candidate and job alignment features."""

    # LinkedIn internal industry / domain category codes from Kaggle dataset mappings
    KNOWN_CATEGORY_CODES = LINKEDIN_CATEGORY_CODES

    # Curated regex taxonomy for extracting genuine professional and technical skills
    REGEX_SKILL_PATTERNS = {
        "Python": r"\bpython\b",
        "Java": r"\bjava\b(?!\s*script)",
        "JavaScript": r"\b(javascript|js|ecmascript)\b",
        "TypeScript": r"\b(typescript|ts)\b",
        "C/C++": r"\b(c\s*(?:\+\+|#|\/|\s*and\s*c\+\+)|c\s*programming|c\s*language|embedded\s*c)\b",
        "C#": r"\b(c#|c\s*sharp|\.net)\b",
        "SQL": r"\b(sql|mysql|postgresql|postgres|pl\/sql|t-sql|sqlite)\b",
        "HTML/CSS": r"\b(html5?|css3?)\b",
        "React": r"\b(react(?:\.js|js|\s*native)?)\b(?!\s*(?:to|with|appropriately|quickly|calmly|in))",
        "FastAPI": r"\b(fastapi|fast\s*api)\b",
        "Django": r"\bdjango\b",
        "Flask": r"\bflask\b",
        "Spring Boot": r"\b(spring\s*boot|spring\s*framework)\b",
        "Node.js": r"\b(node(?:\.js|js)?)\b",
        "Docker": r"\bdocker\b",
        "Kubernetes": r"\b(kubernetes|k8s)\b",
        "AWS": r"\b(aws|amazon\s*web\s*services)\b",
        "Azure": r"\b(azure|microsoft\s*azure)\b",
        "GCP": r"\b(gcp|google\s*cloud)\b",
        "Git/GitHub": r"\b(git|github|gitlab)\b",
        "Linux": r"\b(linux|unix|ubuntu|centos)\b",
        "REST API": r"\b(rest(?:\s*apis?|\s*framework)?|restful|graphql|microservices)\b",
        "Machine Learning": r"\b(machine\s*learning|deep\s*learning|pytorch|tensorflow|keras|scikit-learn|nlp|computer\s*vision)\b",
        "Data Science": r"\b(data\s*science|data\s*analytics?|pandas|numpy|spark)\b",
        "Blender/3D": r"\b(blender\s*3d|3d\s*(?:modeling|artist|animation)|autocad|solidworks)\b",
        "Figma/Design": r"\b(figma|canva|ui\/ux|graphic\s*design)\b",
        "Dental Care": r"\b(dental(?:\s*hygiene|\s*hygienist|\s*assistant)?|dentistry|teeth)\b",
        "Nursing/Patient Care": r"\b(registered\s*nurse|nursing|patient\s*care|triage|clinical\s*care|phlebotomy)\b",
        "Medical Certifications": r"\b(cpr|bls|acls|hipaa)\b",
        "Legal": r"\b(attorney|lawyer|legal\s*research|litigation|paralegal)\b",
        "Accounting/Finance": r"\b(accounting|gaap|cpa|auditing|tax\s*return|bookkeeping|quickbooks)\b",
    }

    DEGREE_HIERARCHY = {
        "phd": 4,
        "doctorate": 4,
        "ph.d": 4,
        "master": 3,
        "m.s": 3,
        "ms": 3,
        "m.sc": 3,
        "mba": 3,
        "m.tech": 3,
        "bachelor": 2,
        "b.s": 2,
        "bs": 2,
        "b.a": 2,
        "ba": 2,
        "b.tech": 2,
        "b.e": 2,
        "associate": 1,
        "bootcamp": 1,
        "certificate": 1,
        "diploma": 1,
    }

    @classmethod
    def is_skill_match(cls, cand_skill: str, job_skill: str) -> bool:
        """Robust comparison preventing single-letter collisions or category code leaks."""
        cs = cand_skill.strip().lower()
        js = job_skill.strip().lower()
        if not cs or not js:
            return False

        # Category codes never match
        if cs.upper() in cls.KNOWN_CATEGORY_CODES or js.upper() in cls.KNOWN_CATEGORY_CODES:
            return False

        # Guard against single-letter / two-letter substring collisions (e.g. 'c' vs 'hcpr' or 'cpr')
        if (cs == "c" or js == "c") and cs != js:
            if cs == "c" and ("c++" in js or "c/c++" in js or "c programming" in js):
                return True
            if js == "c" and ("c++" in cs or "c/c++" in cs or "c programming" in cs):
                return True
            return False

        # Guard against Java matching JavaScript
        if (cs == "java" and "javascript" in js) or (js == "java" and "javascript" in cs):
            return False

        # Direct match
        if cs == js:
            return True

        # Taxonomy group matching
        skill_groups = {
            "Python": ["python", "py"],
            "Java": ["java"],
            "JavaScript": ["javascript", "js", "ecmascript"],
            "TypeScript": ["typescript", "ts"],
            "C/C++": ["c", "c++", "c/c++", "c programming", "embedded c"],
            "C#": ["c#", "c sharp", ".net"],
            "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "dbms"],
            "HTML/CSS": ["html", "css", "html5", "css3", "web technologies"],
            "React": ["react", "react.js", "reactjs", "react native"],
            "FastAPI": ["fastapi", "fast api"],
            "Spring Boot": ["spring boot", "spring"],
            "Node.js": ["node.js", "node", "nodejs"],
            "Git/GitHub": ["git", "github", "gitlab"],
            "Machine Learning": ["machine learning", "deep learning", "nlp", "pytorch", "tensorflow"],
            "Data Science": ["data science", "data analytics", "data structures", "pandas", "numpy"],
            "Blender/3D": ["blender", "blender & creative design", "blender (basics)", "3d modeling"],
            "Figma/Design": ["figma", "canva", "creative design"],
            "Dental Care": ["dental", "dental hygiene", "dentistry"],
            "Nursing/Patient Care": ["nursing", "registered nurse", "patient care"],
            "Legal": ["legal", "law", "attorney", "litigation"],
            "Accounting/Finance": ["accounting", "finance", "gaap", "auditing"],
        }

        for group_name, members in skill_groups.items():
            cs_in_group = any(m == cs or (len(m) >= 3 and m in cs) for m in members)
            js_in_group = (js == group_name.lower()) or any(m == js or (len(m) >= 3 and m in js) for m in members)
            if cs_in_group and js_in_group:
                return True

        # Multi-word phrase word-boundary matching
        if len(cs) >= 4 and re.search(r"\b" + re.escape(cs) + r"\b", js):
            return True
        if len(js) >= 4 and re.search(r"\b" + re.escape(js) + r"\b", cs):
            return True

        return False

    @classmethod
    def extract_job_skills(
        cls, description: str, title: str = "", raw_job_skills: Optional[List[str]] = None
    ) -> List[str]:
        """Extract genuine skill names from description, title, and raw skills, filtering out category codes."""
        extracted: List[str] = []

        # 1. Keep valid non-category skills from raw_job_skills
        if raw_job_skills:
            for s in raw_job_skills:
                s_clean = s.strip()
                if not s_clean:
                    continue
                if s_clean.upper() in cls.KNOWN_CATEGORY_CODES:
                    continue
                extracted.append(s_clean)

        # 2. Extract from title and description using regex taxonomy (stripping URLs and HTML tags first)
        clean_desc = re.sub(r"<[^>]+>", " ", f"{title}\n{description}".lower())
        clean_desc = re.sub(r"https?://\S+|www\.\S+|\b\S+\.(?:html?|com|org|net|io|co|gov|edu)\S*", " ", clean_desc)
        for skill_name, pat in cls.REGEX_SKILL_PATTERNS.items():
            if re.search(pat, clean_desc):
                if not any(cls.is_skill_match(skill_name, ex) for ex in extracted):
                    extracted.append(skill_name)

        return extracted

    @staticmethod
    def extract_candidate_years(parsed_data: dict) -> float:
        """Estimate candidate total years of experience from parsed work history and projects."""
        experiences = parsed_data.get("experience", [])
        current_year = datetime.now().year
        total_months = 0

        if experiences and isinstance(experiences, list):
            for exp in experiences:
                if not isinstance(exp, dict):
                    continue

                start_str = str(exp.get("start_date") or "").strip()
                end_str = str(exp.get("end_date") or "").strip()
                is_current = bool(exp.get("is_current", False))

                start_years = re.findall(r"\b(19\d\d|20\d\d)\b", start_str)
                start_year = int(start_years[0]) if start_years else None

                if is_current or "present" in end_str.lower() or "current" in end_str.lower():
                    end_year = current_year
                else:
                    end_years = re.findall(r"\b(19\d\d|20\d\d)\b", end_str)
                    end_year = int(end_years[0]) if end_years else None

                if start_year and end_year and end_year >= start_year:
                    months = max(6, (end_year - start_year) * 12)
                    total_months += months
                elif start_year:
                    total_months += 12
                else:
                    total_months += 12

        # If candidate has no formal experience but has portfolio projects, credit 0.3 yrs per project
        projects = parsed_data.get("projects", [])
        if total_months == 0 and projects and isinstance(projects, list):
            total_months = min(18, len(projects) * 4)

        estimated_years = round(total_months / 12.0, 1)
        return min(40.0, max(0.0, estimated_years))

    @staticmethod
    def extract_job_required_years(description: str, title: str) -> float:
        """Extract required years of experience from job description and seniority keywords."""
        text = f"{title}\n{description}".lower()

        match = re.search(r"(\d{1,2})\+?\s*(?:to|-)\s*\d{1,2}\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?", text)
        if match:
            return float(match.group(1))

        match_single = re.search(r"(?:minimum|at least|require[ds]?)\s+(\d{1,2})\+?\s*(?:years?|yrs?)", text)
        if match_single:
            return float(match_single.group(1))

        match_simple = re.search(r"(\d{1,2})\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?", text)
        if match_simple:
            val = float(match_simple.group(1))
            if 1 <= val <= 20:
                return val

        t = title.lower()
        if any(w in t for w in ["principal", "staff", "director", "vp", "head of"]):
            return 8.0
        if any(w in t for w in ["lead", "architect", "manager"]):
            return 6.0
        if any(w in t for w in ["senior", "sr."]):
            return 5.0
        if any(w in t for w in ["mid", "intermediate"]):
            return 3.0
        if any(w in t for w in ["junior", "jr.", "entry", "associate", "graduate", "intern", "trainee"]):
            return 1.0

        return 2.0

    @classmethod
    def classify_job_skills(
        cls, description: str, job_skills: List[str], title: str = ""
    ) -> Tuple[List[str], List[str]]:
        """Separate job skills into must-have and nice-to-have based on context or heuristic split."""
        clean_skills = cls.extract_job_skills(description, title, job_skills)
        if not clean_skills:
            return [], []

        desc_lower = description.lower()
        must_have: List[str] = []
        nice_to_have: List[str] = []

        must_keywords = ["requirements", "qualifications", "must have", "what you'll need", "required skills", "minimum qualifications", "basic qualifications"]
        nice_keywords = ["preferred", "nice to have", "plus", "bonus", "optional", "good to have", "desired"]

        has_must_section = any(kw in desc_lower for kw in must_keywords)
        has_nice_section = any(kw in desc_lower for kw in nice_keywords)

        if has_must_section and has_nice_section:
            for skill in clean_skills:
                skill_pat = re.escape(skill.lower())
                pos = desc_lower.find(skill_pat)
                if pos != -1:
                    must_dist = min([pos - desc_lower.rfind(kw, 0, pos) for kw in must_keywords if desc_lower.rfind(kw, 0, pos) != -1] or [999999])
                    nice_dist = min([pos - desc_lower.rfind(kw, 0, pos) for kw in nice_keywords if desc_lower.rfind(kw, 0, pos) != -1] or [999999])
                    if nice_dist < must_dist:
                        nice_to_have.append(skill)
                    else:
                        must_have.append(skill)
                else:
                    must_have.append(skill)
        else:
            split_idx = max(1, int(len(clean_skills) * 0.60))
            must_have = clean_skills[:split_idx]
            nice_to_have = clean_skills[split_idx:]

        return must_have, nice_to_have

    @classmethod
    def extract_education_level(cls, education: List[dict]) -> int:
        """Map candidate education degree to ordinal hierarchy (0 to 4)."""
        if not education or not isinstance(education, list):
            return 0

        max_level = 0
        for edu in education:
            if not isinstance(edu, dict):
                continue
            deg_text = f"{edu.get('degree', '')} {edu.get('field_of_study', '')}".lower()
            for kw, lvl in cls.DEGREE_HIERARCHY.items():
                if re.search(r"\b" + re.escape(kw) + r"\b", deg_text):
                    max_level = max(max_level, lvl)

        return max(1, max_level) if education else 0

    @classmethod
    def extract_job_education_level(cls, description: str) -> int:
        """Extract minimum degree requirement from job description."""
        text = description.lower()
        for kw, lvl in cls.DEGREE_HIERARCHY.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return lvl
        return 2

    @classmethod
    def calculate_title_similarity(
        cls,
        candidate_titles: List[str],
        job_title: str,
        education_entries: Optional[List[dict]] = None,
        candidate_skills: Optional[List[str]] = None,
    ) -> float:
        """Compute semantic role overlap between candidate background and job title."""
        if not job_title:
            return 0.0

        stop_words = {
            "senior", "junior", "lead", "staff", "principal", "the", "and", "in",
            "of", "for", "at", "registered", "i", "ii", "iii", "mid", "entry",
            "part", "time", "full", "remote", "guide",
        }
        job_tokens = set(re.findall(r"\w+", job_title.lower()))
        job_tokens = {t for t in job_tokens if t not in stop_words and len(t) > 2}

        if not job_tokens:
            return 0.5

        # 1. Direct candidate role titles
        cand_tokens = set()
        for title in (candidate_titles or []):
            t_tokens = set(re.findall(r"\w+", str(title).lower()))
            cand_tokens.update({t for t in t_tokens if t not in stop_words and len(t) > 2})

        # 2. If student / no prior formal titles, infer domain from education and technical skills
        if not cand_tokens:
            for edu in (education_entries or []):
                field = str(edu.get("field_of_study") or "").lower()
                cand_tokens.update({t for t in re.findall(r"\w+", field) if t not in stop_words and len(t) > 2})

            tech_markers = {"python", "java", "c++", "c", "javascript", "html", "css", "sql", "react", "fastapi"}
            if any(s.lower() in tech_markers for s in (candidate_skills or [])):
                cand_tokens.update({"software", "engineer", "developer", "technology", "web", "data", "programmer", "analyst"})

        if not cand_tokens:
            return 0.0

        intersection = job_tokens.intersection(cand_tokens)
        if not intersection:
            return 0.0

        score = len(intersection) / len(job_tokens)
        return round(min(1.0, score), 4)

    @classmethod
    def extract_features(
        cls,
        parsed_resume: dict,
        job_title: str,
        job_description: str,
        job_skills: List[str],
        semantic_distance: float,
    ) -> Tuple[FeatureBreakdown, SkillsBreakdown]:
        """Synthesize all pairwise features between candidate resume and job posting."""
        # 1. Semantic similarity
        semantic_sim = round(max(0.0, min(1.0, 1.0 - float(semantic_distance))), 4)

        # 2. Candidate skill aggregation
        candidate_skills = [s.strip() for s in parsed_resume.get("skills", []) if s and isinstance(s, str)]
        for proj in parsed_resume.get("projects", []):
            if isinstance(proj, dict):
                for tech in proj.get("technologies", []):
                    if tech and isinstance(tech, str) and tech.strip() not in candidate_skills:
                        candidate_skills.append(tech.strip())

        # Extract genuine job requirements
        must_have, nice_to_have = cls.classify_job_skills(job_description, job_skills, job_title)

        matched_skills: List[str] = []
        missing_must: List[str] = []
        missing_nice: List[str] = []

        for req in must_have:
            match_found = any(cls.is_skill_match(cs, req) for cs in candidate_skills)
            if match_found:
                matched_skills.append(req)
            else:
                missing_must.append(req)

        for req in nice_to_have:
            match_found = any(cls.is_skill_match(cs, req) for cs in candidate_skills)
            if match_found:
                matched_skills.append(req)
            else:
                missing_nice.append(req)

        matched_skills = list(dict.fromkeys(matched_skills))

        # Skill match ratios
        if must_have:
            must_have_ratio = round((len(must_have) - len(missing_must)) / len(must_have), 4)
        else:
            must_have_ratio = 0.0

        if nice_to_have:
            nice_to_have_ratio = round((len(nice_to_have) - len(missing_nice)) / len(nice_to_have), 4)
        else:
            nice_to_have_ratio = 0.0

        # 3. Experience & Penalty
        cand_years = cls.extract_candidate_years(parsed_resume)
        job_years = cls.extract_job_required_years(job_description, job_title)

        deficit = max(0.0, round(job_years - cand_years, 2))
        threshold = settings.EXPERIENCE_PENALTY_THRESHOLD

        if deficit > threshold:
            penalty = round(min(0.35, (deficit - threshold) * settings.EXPERIENCE_PENALTY_FACTOR), 4)
        else:
            penalty = 0.0

        # 4. Education level match
        cand_edu = cls.extract_education_level(parsed_resume.get("education", []))
        job_edu = cls.extract_job_education_level(job_description)
        if cand_edu >= job_edu:
            edu_match = 1.0
        else:
            edu_match = round(max(0.4, 1.0 - (job_edu - cand_edu) * 0.25), 4)

        # 5. Title & Domain similarity
        cand_titles = [
            exp.get("title", "") for exp in parsed_resume.get("experience", []) if isinstance(exp, dict) and exp.get("title")
        ]
        title_sim = cls.calculate_title_similarity(
            candidate_titles=cand_titles,
            job_title=job_title,
            education_entries=parsed_resume.get("education", []),
            candidate_skills=candidate_skills,
        )

        features = FeatureBreakdown(
            semantic_similarity=semantic_sim,
            must_have_skill_match=must_have_ratio,
            nice_to_have_skill_match=nice_to_have_ratio,
            candidate_years_experience=cand_years,
            job_required_years=job_years,
            experience_deficit=deficit,
            experience_penalty=penalty,
            education_level_match=edu_match,
            title_similarity=title_sim,
        )

        skills_breakdown = SkillsBreakdown(
            matched_skills=matched_skills,
            missing_must_have=missing_must,
            missing_nice_to_have=missing_nice,
        )

        return features, skills_breakdown


# ------------------------------------------------------------------------------
# Composite Scorer
# ------------------------------------------------------------------------------
class CompositeScorer:
    """Calculates transparent rule-based composite alignment scores."""

    @staticmethod
    def calculate_score(features: FeatureBreakdown) -> float:
        """Compute composite score incorporating skills, title alignment, and experience penalty."""
        if features.job_required_years <= 0:
            exp_ratio = 1.0
        else:
            exp_ratio = min(1.0, features.candidate_years_experience / features.job_required_years)

        # Weighted component sum
        raw_score = (
            settings.WEIGHT_SEMANTIC * features.semantic_similarity
            + settings.WEIGHT_MUST_HAVE * features.must_have_skill_match
            + settings.WEIGHT_NICE_TO_HAVE * features.nice_to_have_skill_match
            + settings.WEIGHT_EXPERIENCE * exp_ratio
            + settings.WEIGHT_EDUCATION * features.education_level_match
        )

        # Role alignment multiplier: penalizes jobs outside candidate's professional trajectory
        if features.title_similarity == 0.0 and features.must_have_skill_match == 0.0:
            return 0.0
        elif features.title_similarity == 0.0:
            raw_score *= 0.40
        else:
            raw_score = raw_score * (0.60 + 0.40 * features.title_similarity)

        penalized_score = raw_score - features.experience_penalty
        return round(max(0.0, min(1.0, penalized_score)), 4)


# ------------------------------------------------------------------------------
# XGBoost & SHAP Re-ranking Engine
# ------------------------------------------------------------------------------
class XGBoostExplainer:
    """Machine learning re-ranking model with local SHAP feature explanations."""

    FEATURE_NAMES = [
        "semantic_similarity",
        "must_have_skill_match",
        "nice_to_have_skill_match",
        "experience_ratio",
        "experience_penalty",
        "education_level_match",
        "title_similarity",
    ]

    FEATURE_DISPLAY_NAMES = {
        "semantic_similarity": "Semantic Profile Fit",
        "must_have_skill_match": "Must-Have Skills",
        "nice_to_have_skill_match": "Preferred Skills",
        "experience_ratio": "Years of Experience",
        "experience_penalty": "Experience Gap Penalty",
        "education_level_match": "Education Level",
        "title_similarity": "Role Title Alignment",
    }

    def __init__(self):
        self.model = None
        self.explainer = None
        self._initialize_model()

    def _initialize_model(self):
        """Load persisted model artifact or train a calibrated initial model."""
        import xgboost as xgb
        import shap

        model_path = settings.MATCHER_MODEL_PATH
        if os.path.exists(model_path):
            try:
                self.model = xgb.XGBRegressor()
                self.model.load_model(model_path)
                self.explainer = shap.TreeExplainer(self.model)
                logger.info(f"Loaded existing XGBoost Matcher model from {model_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to load model from {model_path}: {e}. Retraining.")

        self._train_baseline_model()

    def _train_baseline_model(self):
        """Train and persist a baseline XGBoost model on synthetic realistic pairs."""
        import xgboost as xgb
        import shap

        logger.info("Training calibrated baseline XGBoost Matcher model...")
        np.random.seed(42)
        n_samples = 3000

        semantic = np.random.uniform(0.1, 0.95, n_samples)
        must_have = np.random.beta(1.5, 2, n_samples)
        nice_have = np.random.beta(1.2, 2, n_samples)
        exp_ratio = np.random.uniform(0.1, 1.5, n_samples)
        penalty = np.where(exp_ratio < 0.6, np.random.uniform(0.08, 0.30, n_samples), 0.0)
        edu = np.random.choice([0.4, 0.7, 1.0], size=n_samples, p=[0.2, 0.3, 0.5])
        title = np.random.uniform(0.0, 1.0, n_samples)

        X = np.column_stack([
            semantic,
            must_have,
            nice_have,
            np.minimum(1.0, exp_ratio),
            penalty,
            edu,
            title,
        ])

        y = (
            0.15 * semantic
            + 0.40 * must_have
            + 0.10 * nice_have
            + 0.12 * np.minimum(1.0, exp_ratio)
            + 0.08 * edu
            + 0.20 * title
            - 1.20 * penalty
            + 0.05 * (must_have * title)
            + np.random.normal(0, 0.02, n_samples)
        )
        y = np.clip(y, 0.0, 1.0)

        model = xgb.XGBRegressor(
            n_estimators=75,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="reg:squarederror",
            random_state=42,
        )
        model.fit(X, y)

        os.makedirs(os.path.dirname(settings.MATCHER_MODEL_PATH), exist_ok=True)
        model.save_model(settings.MATCHER_MODEL_PATH)

        self.model = model
        self.explainer = shap.TreeExplainer(self.model)
        logger.info(f"Calibrated baseline model successfully saved to {settings.MATCHER_MODEL_PATH}")

    def predict_and_explain(
        self,
        features: FeatureBreakdown,
        skills_breakdown: SkillsBreakdown,
    ) -> Tuple[float, List[ShapExplanation]]:
        """Predict match probability and compute local SHAP feature contributions."""
        if self.model is None or self.explainer is None:
            self._initialize_model()

        exp_ratio = (
            min(1.0, features.candidate_years_experience / features.job_required_years)
            if features.job_required_years > 0
            else 1.0
        )

        x_vec = np.array([[
            features.semantic_similarity,
            features.must_have_skill_match,
            features.nice_to_have_skill_match,
            exp_ratio,
            features.experience_penalty,
            features.education_level_match,
            features.title_similarity,
        ]])

        pred_score = float(self.model.predict(x_vec)[0])
        pred_score = round(max(0.0, min(1.0, pred_score)), 4)

        shap_values = self.explainer.shap_values(x_vec)[0]

        explanations: List[ShapExplanation] = []
        for i, feat_name in enumerate(self.FEATURE_NAMES):
            s_val = float(shap_values[i])
            pct_impact = s_val * 100
            sign = "+" if pct_impact >= 0 else ""
            impact_str = f"{sign}{pct_impact:.1f}%"

            description = self._generate_feature_rationale(
                feat_name, s_val, features, skills_breakdown
            )

            explanations.append(
                ShapExplanation(
                    feature_name=feat_name,
                    display_name=self.FEATURE_DISPLAY_NAMES.get(feat_name, feat_name),
                    shap_value=round(s_val, 4),
                    impact=impact_str,
                    description=description,
                )
            )

        explanations.sort(key=lambda item: abs(item.shap_value), reverse=True)
        return pred_score, explanations

    def _generate_feature_rationale(
        self,
        feature_name: str,
        shap_val: float,
        f: FeatureBreakdown,
        skills: SkillsBreakdown,
    ) -> str:
        """Create human-readable qualitative rationale based on feature value and SHAP direction."""
        if feature_name == "must_have_skill_match":
            if f.must_have_skill_match >= 0.7:
                matched_preview = ", ".join(skills.matched_skills[:3]) or "required skills"
                return f"Strong alignment with mandatory job requirements (matched {matched_preview})."
            elif skills.missing_must_have:
                missing_preview = ", ".join(skills.missing_must_have[:3])
                return f"Missing key mandatory requirements: {missing_preview}."
            elif f.must_have_skill_match == 0.0:
                return "Zero mandatory technical requirements matched for this position."
            return f"Partially matched core required skills ({f.must_have_skill_match*100:.0f}%)."

        if feature_name == "nice_to_have_skill_match":
            if f.nice_to_have_skill_match >= 0.6:
                return "Bonus qualifications and preferred technologies satisfied."
            elif skills.missing_nice_to_have:
                return f"Preferred bonus skills could improve competitiveness: {', '.join(skills.missing_nice_to_have[:2])}."
            return "Preferred skill criteria evaluated."

        if feature_name == "experience_penalty":
            if f.experience_penalty > 0:
                return (
                    f"Experience deficit of {f.experience_deficit:.1f} yrs exceeds the {settings.EXPERIENCE_PENALTY_THRESHOLD:.1f} yr tolerance threshold."
                )
            return "Candidate meets or exceeds minimum required experience."

        if feature_name == "experience_ratio":
            if f.candidate_years_experience >= f.job_required_years:
                return f"Sufficient career tenure ({f.candidate_years_experience:.1f} yrs vs {f.job_required_years:.1f} yrs required)."
            return f"Years of experience ({f.candidate_years_experience:.1f} yrs) below stated target ({f.job_required_years:.1f} yrs)."

        if feature_name == "semantic_similarity":
            if f.semantic_similarity >= 0.60:
                return f"High semantic and domain context alignment ({f.semantic_similarity*100:.0f}% similarity)."
            return f"Low semantic text similarity with role expectations ({f.semantic_similarity*100:.0f}%)."

        if feature_name == "education_level_match":
            if f.education_level_match >= 1.0:
                return "Meets or exceeds degree qualification expectations."
            return "Degree level below typical requirements for this seniority."

        if feature_name == "title_similarity":
            if f.title_similarity >= 0.5:
                return "Directly relevant prior job titles and role trajectories."
            elif f.title_similarity == 0.0:
                return "Target job title does not match candidate's field or technical trajectory."
            return "Prior titles reflect related or non-traditional background."

        return f"Feature contribution: {shap_val:+.2f}"


# ------------------------------------------------------------------------------
# Matcher Agent Orchestrator
# ------------------------------------------------------------------------------
class MatcherAgent:
    """End-to-end matchmaking and explainability orchestrator."""

    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        self.composite_scorer = CompositeScorer()
        self.ml_explainer = XGBoostExplainer()

    async def match_jobs_for_resume(
        self,
        resume_id: str,
        db: AsyncSession,
        limit: int = 10,
        min_score: float = 0.0,
        location: Optional[str] = None,
        remote_only: bool = False,
    ) -> ResumeMatchResponse:
        """Find and rank matching job postings for a candidate resume."""
        # 1. Fetch resume
        res_stmt = select(Resume).where(Resume.id == resume_id)
        res_res = await db.execute(res_stmt)
        resume = res_res.scalar_one_or_none()

        if not resume and resume_id in ("46ca6338-3b1a-4bfc-96e1-5b2a661348e4", "demo-resume"):
            fallback_stmt = select(Resume).order_by(Resume.created_at.desc()).limit(1)
            fallback_res = await db.execute(fallback_stmt)
            resume = fallback_res.scalar_one_or_none()

        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        if resume.embedding is None:
            embed_text = embedding_service.construct_embed_text(resume.parsed_data)
            resume.embedding = await embedding_service.get_embedding(embed_text)
            await db.commit()

        # 2. Hybrid Retrieval:
        # A. Vector similarity search pool
        candidate_pool_limit = max(limit * 4, 60)
        vector_stmt = (
            select(
                JobPosting,
                JobPosting.embedding.cosine_distance(resume.embedding).label("distance"),
            )
            .where(JobPosting.embedding.is_not(None))
        )
        if location:
            vector_stmt = vector_stmt.where(JobPosting.location.ilike(f"%{location}%"))
        if remote_only:
            vector_stmt = vector_stmt.where(JobPosting.remote_allowed.is_(True))

        vector_stmt = vector_stmt.order_by("distance").limit(candidate_pool_limit)
        vector_res = await db.execute(vector_stmt)
        candidate_rows = list(vector_res.all())

        # B. Direct domain & skill retrieval to augment candidate pool
        seen_job_ids = {row[0].id for row in candidate_rows}
        candidate_skills = resume.parsed_data.get("skills", []) if resume.parsed_data else []
        
        # Check if candidate is in tech / software domain
        is_tech = any(
            s.lower() in ["python", "java", "c", "c++", "javascript", "html", "css", "sql", "react", "fastapi"]
            for s in candidate_skills
        ) or any(
            any(w in str(e.get("field_of_study", "")).lower() for w in ["computer", "intelligence", "data", "software", "engineering"])
            for e in (resume.parsed_data.get("education", []) if resume.parsed_data else [])
        )

        query_keywords = []
        if is_tech:
            query_keywords.extend(["software", "developer", "engineer", "data", "web"])
        for s in candidate_skills:
            s_clean = s.lower().strip()
            if len(s_clean) >= 3 and s_clean.upper() not in FeatureExtractor.KNOWN_CATEGORY_CODES:
                if s_clean not in query_keywords:
                    query_keywords.append(s_clean)
            if len(query_keywords) >= 8:
                break

        if query_keywords:
            kw_filters = [JobPosting.title.ilike(f"%{kw}%") for kw in query_keywords]
            kw_stmt = (
                select(
                    JobPosting,
                    JobPosting.embedding.cosine_distance(resume.embedding).label("distance"),
                )
                .where(or_(*kw_filters))
            )
            if location:
                kw_stmt = kw_stmt.where(JobPosting.location.ilike(f"%{location}%"))
            if remote_only:
                kw_stmt = kw_stmt.where(JobPosting.remote_allowed.is_(True))
            kw_stmt = kw_stmt.limit(60)
            kw_res = await db.execute(kw_stmt)
            for row in kw_res.all():
                if row[0].id not in seen_job_ids:
                    candidate_rows.append(row)
                    seen_job_ids.add(row[0].id)


        match_items: List[JobMatchItem] = []

        # 3. Score & re-rank each candidate job
        for row in candidate_rows:
            job: JobPosting = row[0]
            distance: float = float(row.distance)

            skills_list = job.skills if isinstance(job.skills, list) else []
            features, skills_breakdown = self.feature_extractor.extract_features(
                parsed_resume=resume.parsed_data,
                job_title=job.title,
                job_description=job.description,
                job_skills=skills_list,
                semantic_distance=distance,
            )

            composite_score = self.composite_scorer.calculate_score(features)
            xgb_score, explanations = self.ml_explainer.predict_and_explain(
                features, skills_breakdown
            )

            final_score = round(0.55 * xgb_score + 0.45 * composite_score, 4)

            if final_score < min_score:
                continue

            match_items.append(
                JobMatchItem(
                    job_id=job.id,
                    title=job.title,
                    company_name=job.company_name,
                    location=job.location,
                    work_type=job.work_type,
                    remote_allowed=bool(job.remote_allowed),
                    semantic_score=features.semantic_similarity,
                    composite_score=composite_score,
                    xgboost_score=xgb_score,
                    final_score=final_score,
                    rank=0,
                    skills_breakdown=skills_breakdown,
                    features=features,
                    explanations=explanations,
                )
            )

        # 4. Sort by final score descending and assign rank
        match_items.sort(key=lambda m: m.final_score, reverse=True)
        top_matches = match_items[:limit]
        for rank_idx, item in enumerate(top_matches, start=1):
            item.rank = rank_idx

        return ResumeMatchResponse(
            resume_id=resume.id,
            candidate_name=resume.candidate_name,
            total_matches=len(top_matches),
            matches=top_matches,
        )

    async def match_candidates_for_job(
        self,
        job_id: str,
        db: AsyncSession,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> JobCandidatesMatchResponse:
        """Find and rank candidate resumes for a specific job posting."""
        job_stmt = select(JobPosting).where(JobPosting.id == job_id)
        job_res = await db.execute(job_stmt)
        job = job_res.scalar_one_or_none()

        if not job:
            raise ValueError(f"Job posting with ID '{job_id}' not found.")

        if job.embedding is None:
            embed_text = embedding_service.construct_job_embed_text(
                title=job.title,
                description=job.description,
                skills=job.skills if isinstance(job.skills, list) else [],
                company=job.company_name or "",
                location=job.location or "",
            )
            job.embedding = await embedding_service.get_embedding(embed_text)
            await db.commit()

        candidate_pool_limit = max(limit * 4, 40)
        res_stmt = (
            select(
                Resume,
                Resume.embedding.cosine_distance(job.embedding).label("distance"),
            )
            .where(Resume.embedding.is_not(None))
            .order_by("distance")
            .limit(candidate_pool_limit)
        )
        res_res = await db.execute(res_stmt)
        candidates = res_res.all()

        candidate_items: List[CandidateMatchItem] = []
        skills_list = job.skills if isinstance(job.skills, list) else []

        for row in candidates:
            resume: Resume = row[0]
            distance: float = float(row.distance)

            features, skills_breakdown = self.feature_extractor.extract_features(
                parsed_resume=resume.parsed_data,
                job_title=job.title,
                job_description=job.description,
                job_skills=skills_list,
                semantic_distance=distance,
            )

            composite_score = self.composite_scorer.calculate_score(features)
            xgb_score, explanations = self.ml_explainer.predict_and_explain(
                features, skills_breakdown
            )
            final_score = round(0.55 * xgb_score + 0.45 * composite_score, 4)

            if final_score < min_score:
                continue

            candidate_items.append(
                CandidateMatchItem(
                    resume_id=resume.id,
                    candidate_name=resume.candidate_name,
                    email=resume.email,
                    semantic_score=features.semantic_similarity,
                    composite_score=composite_score,
                    xgboost_score=xgb_score,
                    final_score=final_score,
                    rank=0,
                    skills_breakdown=skills_breakdown,
                    features=features,
                    explanations=explanations,
                )
            )

        candidate_items.sort(key=lambda c: c.final_score, reverse=True)
        top_candidates = candidate_items[:limit]
        for rank_idx, item in enumerate(top_candidates, start=1):
            item.rank = rank_idx

        return JobCandidatesMatchResponse(
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
            total_matches=len(top_candidates),
            candidates=top_candidates,
        )

    async def compare_resume_and_job(
        self,
        resume_id: str,
        job_id: str,
        db: AsyncSession,
    ) -> MatchCompareResponse:
        """Deep-dive match analysis and explanation for a specific resume and job posting pair."""
        res_res = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = res_res.scalar_one_or_none()
        if not resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        job_res = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job posting with ID '{job_id}' not found.")

        if resume.embedding is not None and job.embedding is not None:
            r_vec = np.array(resume.embedding)
            j_vec = np.array(job.embedding)
            dot = np.dot(r_vec, j_vec)
            dist = float(max(0.0, 1.0 - dot))
        else:
            dist = 0.40

        skills_list = job.skills if isinstance(job.skills, list) else []
        features, skills_breakdown = self.feature_extractor.extract_features(
            parsed_resume=resume.parsed_data,
            job_title=job.title,
            job_description=job.description,
            job_skills=skills_list,
            semantic_distance=dist,
        )

        composite_score = self.composite_scorer.calculate_score(features)
        xgb_score, explanations = self.ml_explainer.predict_and_explain(
            features, skills_breakdown
        )
        final_score = round(0.55 * xgb_score + 0.45 * composite_score, 4)

        return MatchCompareResponse(
            resume_id=resume.id,
            candidate_name=resume.candidate_name,
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
            semantic_score=features.semantic_similarity,
            composite_score=composite_score,
            xgboost_score=xgb_score,
            final_score=final_score,
            skills_breakdown=skills_breakdown,
            features=features,
            explanations=explanations,
        )


matcher_agent = MatcherAgent()
