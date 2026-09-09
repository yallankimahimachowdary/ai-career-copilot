import json
import re
from typing import List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.schemas.resume import (
    ContactInfo,
    Education,
    ParsedResume,
    Project,
    WorkExperience,
)

COMMON_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Go", "Java", "C++", "C#", "Ruby", "PHP",
    "FastAPI", "Django", "Flask", "React", "Next.js", "Vue", "Angular", "Node.js",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "SQLAlchemy", "Alembic",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "CI/CD", "Git", "GitHub", "Linux",
    "Machine Learning", "Deep Learning", "NLP", "LLMs", "PyTorch", "TensorFlow",
    "REST API", "GraphQL", "Microservices", "Unit Testing", "Pytest", "Agile", "Scrum"
]


class ParserAgent:
    """Intelligent resume parser agent supporting LLM extraction with rule-based fallback."""

    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.openai_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash")

    async def parse(self, raw_text: str) -> ParsedResume:
        """Parse raw resume text into a structured ParsedResume object."""
        if self.openai_key:
            try:
                return await self._parse_with_openai(raw_text)
            except Exception as e:
                logger.warning(f"OpenAI parsing failed: {e}. Falling back to rule-based parser.")

        if self.gemini_key:
            try:
                return await self._parse_with_gemini(raw_text)
            except Exception as e:
                logger.warning(f"Gemini parsing failed: {e}. Falling back to rule-based parser.")

        # Default fallback to heuristic rule-based extraction
        return self._parse_with_rules(raw_text)

    async def _parse_with_openai(self, raw_text: str) -> ParsedResume:
        """Extract structured resume data using OpenAI structured output."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }
            prompt = (
                "You are an expert resume parsing agent. Extract the candidate's structured profile "
                "strictly following the requested JSON schema. Return valid JSON only.\n"
                "STRICT FORMATTING REQUIREMENTS:\n"
                "1. 'skills' MUST be a flat JSON array of strings, NOT grouped by categories or dictionaries.\n"
                "2. 'projects' items MUST use the key 'name' (DO NOT use 'title' or 'project_name').\n"
                "3. 'certifications' MUST be a flat JSON array of strings, NOT objects.\n"
            )
            payload = {
                "model": self.openai_model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Resume Text:\n{raw_text}"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
            }
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = ParsedResume.model_validate(json.loads(content))
            return self._enrich_contact_info(parsed, raw_text)

    async def _parse_with_gemini(self, raw_text: str) -> ParsedResume:
        """Extract structured resume data using Gemini API."""
        model_name = self.gemini_model.removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
        prompt = (
            "You are an expert resume parsing agent. Extract the candidate's profile strictly into JSON format "
            "matching this exact schema:\n"
            "{\n"
            '  "contact_info": {"name": "...", "email": "...", "phone": "...", "location": "...", "linkedin_url": "...", "github_url": "...", "portfolio_url": "..."},\n'
            '  "summary": "...",\n'
            '  "skills": ["Python", "FastAPI", "PostgreSQL"],\n'
            '  "experience": [{"title": "Software Engineer", "company": "Acme Inc", "location": "Remote", "start_date": "Jan 2022", "end_date": "Present", "is_current": true, "description": ["Bullet 1", "Bullet 2"]}],\n'
            '  "education": [{"institution": "MIT", "degree": "B.S.", "field_of_study": "Computer Science", "graduation_year": "2021", "gpa": "3.9"}],\n'
            '  "projects": [{"name": "Career Copilot", "description": "AI agent platform", "technologies": ["Python", "Docker"], "url": "https://github.com/..."}],\n'
            '  "certifications": ["AWS Certified Solutions Architect", "CKA"]\n'
            "}\n\n"
            "STRICT FORMATTING REQUIREMENTS:\n"
            "1. 'skills' MUST be a flat JSON array of strings (e.g. [\"Python\", \"Docker\"]). DO NOT group skills by categories or use a dictionary/object.\n"
            "2. 'projects' array items MUST use the key 'name' (DO NOT use 'title' or 'project_name').\n"
            "3. 'certifications' MUST be a flat JSON array of plain strings (e.g. [\"AWS Certified Solutions Architect\"]). DO NOT return objects or dictionaries.\n"
            "4. Return valid JSON only, without any markdown formatting."
        )
        payload = {
            "contents": [{
                "parts": [{"text": f"{prompt}\n\nResume Text:\n{raw_text}"}]
            }],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            text_content = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = ParsedResume.model_validate(json.loads(text_content))
            return self._enrich_contact_info(parsed, raw_text)

    def _enrich_contact_info(self, parsed: ParsedResume, raw_text: str) -> ParsedResume:
        """Backfill any contact info fields missed by LLM using deterministic regex extraction."""
        if not parsed.contact_info.linkedin_url:
            parsed.contact_info.linkedin_url = self._extract_pattern(raw_text, r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+")
        if not parsed.contact_info.github_url:
            parsed.contact_info.github_url = self._extract_pattern(raw_text, r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+")
        if not parsed.contact_info.email:
            parsed.contact_info.email = self._extract_email(raw_text)
        if not parsed.contact_info.phone:
            parsed.contact_info.phone = self._extract_phone(raw_text)
        return parsed

    def _parse_with_rules(self, raw_text: str) -> ParsedResume:
        """High-precision heuristic rule-based extraction fallback."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        # 1. Contact Info Extraction
        email = self._extract_email(raw_text)
        phone = self._extract_phone(raw_text)
        linkedin = self._extract_pattern(raw_text, r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+")
        github = self._extract_pattern(raw_text, r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+")

        # Candidate name heuristic: first non-contact line with letters
        candidate_name = None
        for line in lines[:5]:
            if not any(x in line.lower() for x in ["@", "http", "resume", "curriculum", "phone", "email"]):
                cleaned = re.sub(r"[^a-zA-Z\s\.]", "", line).strip()
                if 2 <= len(cleaned.split()) <= 4:
                    candidate_name = cleaned
                    break

        contact_info = ContactInfo(
            name=candidate_name,
            email=email,
            phone=phone,
            linkedin_url=linkedin,
            github_url=github,
        )

        # 2. Section Partitioning
        sections = self._split_into_sections(lines)

        # 3. Skills Extraction
        skills = self._extract_skills(raw_text, sections.get("skills", []))

        # 4. Experience Extraction
        experience = self._extract_experience(sections.get("experience", []))

        # 5. Education Extraction
        education = self._extract_education(sections.get("education", []))

        # 6. Projects Extraction
        projects = self._extract_projects(sections.get("projects", []))

        # 7. Summary
        summary = " ".join(sections.get("summary", [])) if sections.get("summary") else None

        return ParsedResume(
            contact_info=contact_info,
            summary=summary,
            skills=skills,
            experience=experience,
            education=education,
            projects=projects,
            certifications=sections.get("certifications", []),
        )

    def _extract_email(self, text: str) -> Optional[str]:
        match = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        return match.group(0) if match else None

    def _extract_pattern(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else None

    def _split_into_sections(self, lines: List[str]) -> dict:
        """Split document lines into logical resume sections."""
        section_headers = {
            "summary": ["summary", "professional summary", "about me", "objective"],
            "skills": ["skills", "technical skills", "core competencies", "skills & tools"],
            "experience": ["experience", "work experience", "professional experience", "employment"],
            "education": ["education", "academic background", "qualifications"],
            "projects": ["projects", "personal projects", "key projects"],
            "certifications": ["certifications", "licenses", "certificates"],
        }

        current_section = "summary"
        sections = {k: [] for k in section_headers}

        for line in lines:
            line_lower = line.lower().strip(":# -")
            matched_section = None
            for sec, keywords in section_headers.items():
                if any(line_lower == kw for kw in keywords) or any(line_lower.startswith(f"{kw}:") for kw in keywords):
                    matched_section = sec
                    break

            if matched_section:
                current_section = matched_section
            else:
                sections[current_section].append(line)

        return sections

    def _extract_skills(self, full_text: str, skill_lines: List[str]) -> List[str]:
        """Extract skills from identified section and matching common keywords."""
        found_skills = set()

        # Check in skills section lines
        for line in skill_lines:
            # Split by commas or pipes
            parts = re.split(r"[,|•·\n]", line)
            for part in parts:
                cleaned = part.strip()
                if cleaned and len(cleaned) < 35 and not any(ch in cleaned for ch in ["@", "http"]):
                    found_skills.add(cleaned)

        # Cross check with common technical skills in entire document
        text_lower = full_text.lower()
        for skill in COMMON_SKILLS:
            # Word boundary check
            if re.search(r"\b" + re.escape(skill.lower()) + r"\b", text_lower):
                found_skills.add(skill)

        return sorted(list(found_skills))

    def _extract_experience(self, exp_lines: List[str]) -> List[WorkExperience]:
        """Extract work experience entries from experience section."""
        entries: List[WorkExperience] = []
        if not exp_lines:
            return entries

        current_title = None
        current_company = None
        current_bullets: List[str] = []

        for line in exp_lines:
            # Check for bullet point
            is_bullet = line.startswith(("-", "•", "*", "–")) or len(current_bullets) > 0
            if " at " in line.lower() or " | " in line or " - " in line and not is_bullet:
                if current_title and current_company:
                    entries.append(WorkExperience(
                        title=current_title,
                        company=current_company,
                        description=current_bullets,
                    ))
                    current_bullets = []

                parts = re.split(r"\s+(?:at|\||-)\s+", line, flags=re.IGNORECASE)
                current_title = parts[0].strip()
                current_company = parts[1].strip() if len(parts) > 1 else "Unknown"
            elif is_bullet:
                cleaned = line.lstrip("-•*– ").strip()
                if cleaned:
                    current_bullets.append(cleaned)
            else:
                if not current_title:
                    current_title = line
                    current_company = "Organization"
                else:
                    current_bullets.append(line)

        if current_title and current_company:
            entries.append(WorkExperience(
                title=current_title,
                company=current_company,
                description=current_bullets,
            ))

        return entries

    def _extract_education(self, edu_lines: List[str]) -> List[Education]:
        """Extract education entries."""
        entries: List[Education] = []
        for line in edu_lines:
            if any(term in line.lower() for term in ["university", "college", "institute", "school", "bachelor", "master", "degree", "b.s", "m.s", "ph.d"]):
                entries.append(Education(
                    institution=line,
                    degree=next((d for d in ["B.S.", "M.S.", "Ph.D.", "Bachelor", "Master"] if d.lower() in line.lower()), None),
                ))
        return entries

    def _extract_projects(self, proj_lines: List[str]) -> List[Project]:
        """Extract projects entries."""
        projects: List[Project] = []
        for line in proj_lines:
            if not line.startswith(("-", "•", "*")):
                projects.append(Project(name=line))
            elif projects:
                projects[-1].description = line.lstrip("-•* ")
        return projects


parser_agent = ParserAgent()
