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
from app.core.taxonomy import CANONICAL_SKILL_PATTERNS, extract_canonical_skills

COMMON_SKILLS = list(CANONICAL_SKILL_PATTERNS.keys())


class ParserAgent:
    """Intelligent resume parser agent supporting LLM extraction with rule-based fallback."""

    def __init__(self):
        self.ollama_base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
        self.openai_key = settings.OPENAI_API_KEY
        self.openai_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    async def parse(self, raw_text: str) -> ParsedResume:
        """Parse raw resume text into a structured ParsedResume object."""
        # 1. Primary extraction via local Ollama LLM
        try:
            return await self._parse_with_ollama(raw_text)
        except Exception as e:
            logger.warning(f"Ollama parsing failed: {e}. Falling back to secondary/rule-based parser.")

        # 2. Secondary fallback via OpenAI if configured
        if self.openai_key:
            try:
                return await self._parse_with_openai(raw_text)
            except Exception as e:
                logger.warning(f"OpenAI parsing failed: {e}. Falling back to rule-based parser.")

        # 3. Default fallback to heuristic rule-based extraction
        return self._parse_with_rules(raw_text)

    def _clean_and_parse_json(self, text_content: str) -> dict:
        """Strip markdown fences, locate JSON delimiters, fix common syntax flaws, and parse."""
        cleaned = text_content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # Attempt direct JSON deserialization
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Locate outer JSON object
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Remove trailing commas before closing braces/brackets
                fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
                return json.loads(fixed)

        raise ValueError(f"Could not extract valid JSON from response: {text_content[:200]}")

    async def _parse_with_ollama(self, raw_text: str) -> ParsedResume:
        """Extract structured resume data using configured LLM provider (Ollama or Gemini)."""
        prompt = (
            "You are an expert resume parsing agent. Extract the candidate's profile strictly into JSON format "
            "matching this exact schema:\n"
            "{\n"
            '  "contact_info": {"name": "", "email": "", "phone": "", "location": "", "linkedin_url": "", "github_url": "", "portfolio_url": ""},\n'
            '  "summary": "",\n'
            '  "skills": [],\n'
            '  "experience": [{"title": "", "company": "", "location": "", "start_date": "", "end_date": "", "is_current": false, "description": []}],\n'
            '  "education": [{"institution": "", "degree": "", "field_of_study": "", "graduation_year": "", "gpa": ""}],\n'
            '  "projects": [{"name": "", "description": "", "technologies": [], "url": ""}],\n'
            '  "certifications": []\n'
            "}\n\n"
            "STRICT FORMATTING REQUIREMENTS:\n"
            "1. 'skills' MUST be a flat JSON array of strings found in the resume. DO NOT invent skills. DO NOT group skills by categories.\n"
            "2. 'projects' array items MUST use the key 'name'. In 'technologies', include ONLY technologies explicitly mentioned for that project in the resume. If none are specified, return []. NEVER copy or hallucinate technologies (such as Docker, Python, etc.) that do not appear in the resume.\n"
            "3. 'certifications' MUST be a flat JSON array of plain strings. DO NOT return objects or dictionaries.\n"
            "4. Return valid JSON only, without any markdown formatting, preamble, or commentary."
        )

        from app.services.llm_provider import get_llm_provider
        provider = get_llm_provider()

        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                full_prompt = f"{prompt}\n\nResume Text:\n{raw_text}"
                resp = await provider.generate_json(
                    prompt=full_prompt,
                    temperature=0.0,
                    max_tokens=1500,
                    keep_alive="30m",
                    timeout=60.0,
                )
                parsed_dict = resp.data
                parsed = ParsedResume.model_validate(parsed_dict)
                return self._enrich_contact_info(parsed, raw_text)
            except Exception as exc:
                last_error = exc
                logger.warning(f"LLM parsing attempt {attempt}/{max_attempts} failed: {exc}")
                if attempt < max_attempts:
                    continue

        raise RuntimeError(f"LLM parser failed after {max_attempts} attempts: {last_error}")

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

    def _enrich_contact_info(self, parsed: ParsedResume, raw_text: str) -> ParsedResume:
        """Backfill any contact info fields missed by LLM using deterministic regex extraction."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if not parsed.contact_info.linkedin_url:
            parsed.contact_info.linkedin_url = self._extract_pattern(
                raw_text, r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+"
            )
        if not parsed.contact_info.github_url:
            parsed.contact_info.github_url = self._extract_pattern(
                raw_text, r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_-]+"
            )
        if not parsed.contact_info.email:
            parsed.contact_info.email = self._extract_email(raw_text)
        if not parsed.contact_info.phone:
            parsed.contact_info.phone = self._extract_phone(raw_text)
        if not parsed.contact_info.location:
            parsed.contact_info.location = self._extract_location(lines)

        location_words = {"nadu", "tamil", "chennai", "bangalore", "mumbai", "delhi", "california", "texas"}
        current_name = (parsed.contact_info.name or "").lower()
        if not parsed.contact_info.name or any(kw in current_name for kw in location_words):
            extracted = self._extract_name(raw_text, lines)
            if extracted:
                parsed.contact_info.name = extracted

        # Enrich skills: augment LLM extracted skills with canonical domain taxonomy matches
        existing_skills_lower = {s.lower() for s in parsed.skills}
        tax_skills = extract_canonical_skills(raw_text)
        for s in tax_skills:
            if s.lower() not in existing_skills_lower:
                parsed.skills.append(s)
                existing_skills_lower.add(s.lower())

        # Post-processing anti-hallucination guardrail:
        # Sanitize project technologies: discard technologies not mentioned in raw_text or project description
        raw_text_lower = raw_text.lower()
        for proj in parsed.projects:
            if proj.technologies:
                filtered_tech = []
                for tech in proj.technologies:
                    tech_clean = tech.strip().lower()
                    if not tech_clean:
                        continue
                    # Check if tech is actually in raw resume text or project description
                    proj_desc = (proj.description or "").lower()
                    if re.search(r"\b" + re.escape(tech_clean) + r"\b", raw_text_lower) or re.search(r"\b" + re.escape(tech_clean) + r"\b", proj_desc):
                        filtered_tech.append(tech)
                proj.technologies = filtered_tech

        return parsed

    def _extract_name(self, raw_text: str, lines: Optional[List[str]] = None) -> Optional[str]:
        """Robust candidate name extractor handling initials (e.g. S.Deepika), prefixes, and filtering locations/titles."""
        if lines is None:
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        disallowed_keywords = {
            "@", "http", "www.", "linkedin", "github", "phone", "email", "tel:", "mobile",
            "resume", "curriculum vitae", "cv", "portfolio", "summary", "objective",
            "education", "skills", "experience", "projects", "certifications", "profile",
        }
        location_keywords = {
            "nadu", "tamil", "chennai", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
            "pune", "kolkata", "california", "texas", "york", "india", "usa", "remote", "san francisco",
        }
        role_keywords = {
            "engineer", "developer", "student", "intern", "manager", "architect", "lead",
            "specialist", "scientist", "analyst", "consultant", "designer", "administrator",
        }

        # Check top header lines
        for line in lines[:10]:
            line_lower = line.lower()
            if any(kw in line_lower for kw in disallowed_keywords):
                continue
            # Location or compound lines with commas should not be candidate names
            if "," in line:
                continue
            # Lines with numbers (dates, phone numbers, addresses) are not names
            if re.search(r"\d", line):
                continue

            # Normalize dotted initials without space: "S.Deepika" -> "S. Deepika"
            norm = re.sub(r"([A-Za-z]\.)([A-Za-z])", r"\1 \2", line).strip()
            # Clean non-alphabetic except spaces and dots
            cleaned = re.sub(r"[^a-zA-Z\s\.]", " ", norm).strip()
            words = cleaned.split()

            if 1 <= len(words) <= 4:
                total_letters = sum(len(w.rstrip(".")) for w in words)
                has_substantive_word = any(len(w.rstrip(".")) >= 2 for w in words)
                if total_letters >= 3 and has_substantive_word:
                    # Filter out location words
                    if any(w.lower().rstrip(".") in location_keywords for w in words):
                        continue
                    # Filter out job roles
                    if any(w.lower().rstrip(".") in role_keywords for w in words):
                        continue
                    return " ".join(words)

        # Fallback: check summary or self-introduction in raw_text
        intro_match = re.search(
            r"(?:i\s+am|my\s+name\s+is)\s+([A-Z][a-zA-Z\.]*(?:\s+[A-Z][a-zA-Z\.]*){1,3})",
            raw_text,
            re.IGNORECASE,
        )
        if intro_match:
            return intro_match.group(1).strip()

        return None

    def _extract_location(self, lines: List[str]) -> Optional[str]:
        """Extract location if present in top contact lines."""
        location_keywords = {
            "nadu", "tamil", "chennai", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
            "pune", "kolkata", "california", "texas", "york", "india", "usa", "remote", "san francisco",
        }
        for line in lines[:10]:
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["@", "http", "linkedin", "github", "phone", "email"]):
                continue
            if "," in line or any(kw in line_lower for kw in location_keywords):
                cleaned = re.sub(r"\s*,\s*", ", ", line).strip()
                cleaned = re.sub(r"[^a-zA-Z0-9\s,\.-]", "", cleaned).strip()
                words = cleaned.split()
                if 2 <= len(words) <= 6:
                    return cleaned
        return None

    def _parse_with_rules(self, raw_text: str) -> ParsedResume:
        """High-precision heuristic rule-based extraction fallback."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        # 1. Contact Info Extraction
        email = self._extract_email(raw_text)
        phone = self._extract_phone(raw_text)
        linkedin = self._extract_pattern(raw_text, r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+")
        github = self._extract_pattern(raw_text, r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_-]+")
        location = self._extract_location(lines)
        candidate_name = self._extract_name(raw_text, lines)

        contact_info = ContactInfo(
            name=candidate_name,
            email=email,
            phone=phone,
            location=location,
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
        match = re.search(r"([\w\.-]+)\s*@\s*([\w\.-]+\.[a-zA-Z]{2,})", text)
        return f"{match.group(1)}@{match.group(2)}" if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        return match.group(0) if match else None

    def _extract_pattern(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        val = match.group(0).strip()
        if ("linkedin.com" in val.lower() or "github.com" in val.lower()) and not val.lower().startswith("http"):
            val = f"https://{val}"
        return val

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

        bullet_chars = ("-", "•", "*", "–", "·", "▪", "▫", "\u2022", "\u2023", "\u2043", "\u2219", "\ufffd")
        current_title = None
        current_company = None
        current_bullets: List[str] = []

        for line in exp_lines:
            stripped = line.strip()
            if not stripped:
                continue

            starts_bullet = any(stripped.startswith(c) for c in bullet_chars)
            is_header = (" at " in stripped.lower() or " | " in stripped or " - " in stripped) and not starts_bullet

            if is_header:
                if current_title and current_company:
                    entries.append(WorkExperience(
                        title=current_title,
                        company=current_company,
                        description=current_bullets,
                    ))
                    current_bullets = []

                parts = re.split(r"\s+(?:at|\||-)\s+", stripped, flags=re.IGNORECASE)
                current_title = parts[0].strip()
                current_company = parts[1].strip() if len(parts) > 1 else "Unknown"
            elif starts_bullet:
                cleaned = re.sub(r"^[\s\-•*–·▪▫\u2022\u2023\u2043\u2219\ufffd]+", "", stripped).strip()
                if cleaned:
                    current_bullets.append(cleaned)
            else:
                # Line without bullet prefix
                is_continuation = False
                if current_bullets:
                    prev = current_bullets[-1]
                    if not prev.endswith((".", "!", "?", ";", ":")):
                        is_continuation = True
                    elif stripped[0].islower() or (len(stripped.split()) <= 4 and stripped.endswith(".")):
                        is_continuation = True

                if is_continuation and current_bullets:
                    current_bullets[-1] = f"{current_bullets[-1]} {stripped}"
                elif not current_title:
                    current_title = stripped
                    current_company = "Organization"
                else:
                    current_bullets.append(stripped)

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
        """Extract projects entries, cleanly merging multi-line wrapped bullet points into single units."""
        projects: List[Project] = []
        if not proj_lines:
            return projects

        bullet_chars = ("-", "•", "*", "–", "·", "▪", "▫", "\u2022", "\u2023", "\u2043", "\u2219", "\ufffd")
        current_project: Optional[Project] = None
        current_bullets: List[str] = []

        for raw_line in proj_lines:
            line = raw_line.strip()
            if not line:
                continue

            starts_bullet = any(line.startswith(c) for c in bullet_chars)
            if starts_bullet:
                cleaned = re.sub(r"^[\s\-•*–·▪▫\u2022\u2023\u2043\u2219\ufffd]+", "", line).strip()
                if cleaned:
                    current_bullets.append(cleaned)
            else:
                # Line does not start with bullet character
                is_continuation = False
                if current_bullets:
                    prev = current_bullets[-1]
                    if not prev.endswith((".", "!", "?", ";", ":")):
                        is_continuation = True
                    elif line[0].islower() or (len(line.split()) <= 4 and line.endswith(".")):
                        is_continuation = True

                if is_continuation and current_bullets:
                    current_bullets[-1] = f"{current_bullets[-1]} {line}"
                else:
                    # New project title line
                    if current_project and current_bullets:
                        current_project.description = " ".join(current_bullets)

                    current_bullets = []
                    cleaned_title = line.strip(":# -")
                    if cleaned_title.lower() not in ["projects", "personal projects", "academic projects"]:
                        current_project = Project(name=cleaned_title, description="")
                        projects.append(current_project)

        if current_project and current_bullets:
            current_project.description = " ".join(current_bullets)

        return projects


parser_agent = ParserAgent()
