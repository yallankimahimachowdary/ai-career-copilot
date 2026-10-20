import json
import re
from typing import List, Optional, Tuple
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
from app.core.taxonomy import (
    CANONICAL_SKILL_PATTERNS,
    SPOKEN_LANGUAGES,
    extract_canonical_skills,
    extract_spoken_languages,
    is_ignored_token,
)

COMMON_SKILLS = list(CANONICAL_SKILL_PATTERNS.keys())

_spacy_nlp = None
_spacy_checked = False


def get_spacy_ner():
    """Lazily load spaCy NER model if available, returning None without error if missing."""
    global _spacy_nlp, _spacy_checked
    if _spacy_checked:
        return _spacy_nlp
    _spacy_checked = True
    try:
        import spacy
        try:
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:
            _spacy_nlp = None
    except ImportError:
        _spacy_nlp = None
    return _spacy_nlp


class ParserAgent:
    """Intelligent resume parser agent supporting LLM extraction with rule-based fallback."""

    def __init__(self):
        self.ollama_base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
        self.openai_key = settings.OPENAI_API_KEY
        self.openai_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    async def parse(
        self,
        raw_text: str,
        metadata: Optional[dict] = None,
        mode: Optional[str] = None,
    ) -> ParsedResume:
        """Parse raw resume text into a structured ParsedResume object.
        
        Supports deterministic rule-based mode (bypasses LLM, outputs canonical skills only),
        LLM mode, or hybrid fallback mode.
        """
        effective_mode = mode or getattr(settings, "PARSER_MODE", "hybrid")
        logger.info(f"[ParserAgent] Executing parser in mode: '{effective_mode}'")

        if effective_mode == "rule_based":
            parsed = self._parse_with_rules(raw_text)
            # Enforce canonical skills only
            parsed.skills = sorted(list(extract_canonical_skills(raw_text)))
            self._apply_metadata(parsed, raw_text, metadata, engine="rules", mode="rule_based")
            return parsed

        # 1. Primary extraction via local Ollama LLM
        try:
            parsed = await self._parse_with_ollama(raw_text)
            self._apply_metadata(parsed, raw_text, metadata, engine="ollama", mode=effective_mode)
            return parsed
        except Exception as e:
            logger.warning(f"Ollama parsing failed: {e}. Falling back to secondary/rule-based parser.")

        # 2. Secondary fallback via OpenAI if configured
        if self.openai_key:
            try:
                parsed = await self._parse_with_openai(raw_text)
                self._apply_metadata(parsed, raw_text, metadata, engine="openai", mode=effective_mode)
                return parsed
            except Exception as e:
                logger.warning(f"OpenAI parsing failed: {e}. Falling back to rule-based parser.")

        # 3. Default fallback to heuristic rule-based extraction
        parsed = self._parse_with_rules(raw_text)
        parsed.skills = sorted(list(extract_canonical_skills(raw_text)))
        self._apply_metadata(parsed, raw_text, metadata, engine="rules", mode=effective_mode)
        return parsed

    def _apply_metadata(
        self,
        parsed: ParsedResume,
        raw_text: str,
        metadata: Optional[dict] = None,
        engine: str = "rules",
        mode: str = "hybrid",
    ) -> None:
        """Attach parsing provenance and extractor metadata to the parsed resume."""
        meta = dict(metadata or {})
        meta["parser_engine"] = engine
        meta["parser_mode"] = mode
        meta["extractor"] = meta.get("extractor", "unknown")
        meta["spacy_ner_available"] = get_spacy_ner() is not None
        parsed.parse_metadata = meta


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

        # Partition skills and tokens into canonical skills, languages, ignored tokens, and other terms
        canonical_set = set()
        other_set = set()
        ignored_set = set(parsed.ignored_tokens or [])
        lang_set = set(parsed.languages or [])

        # Extract languages from raw text
        for lang in extract_spoken_languages(raw_text):
            lang_set.add(lang)

        candidates = list(parsed.skills or []) + list(parsed.other_terms or [])
        for token in candidates:
            token_clean = token.strip()
            if not token_clean:
                continue
            if token_clean.lower() in SPOKEN_LANGUAGES:
                lang_set.add(token_clean.capitalize())
                continue
            matched = extract_canonical_skills(token_clean)
            if matched:
                canonical_set.update(matched)
                continue
            other_set.add(token_clean)
            if is_ignored_token(token_clean):
                ignored_set.add(token_clean)

        # Also extract canonical skills from the full document text
        text_skills = extract_canonical_skills(raw_text)
        canonical_set.update(text_skills)

        parsed.skills = sorted(list(canonical_set))
        parsed.other_terms = sorted(list(other_set))
        parsed.ignored_tokens = sorted(list(ignored_set))
        parsed.languages = sorted(list(lang_set))

        # Safeguard: backfill education if empty
        if not parsed.education:
            parsed.education = self._extract_education(raw_text, [])

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
                    proj_desc = (proj.description or "").lower()
                    if re.search(r"\b" + re.escape(tech_clean) + r"\b", raw_text_lower) or re.search(r"\b" + re.escape(tech_clean) + r"\b", proj_desc):
                        filtered_tech.append(tech)
                proj.technologies = filtered_tech

        return parsed

    def _extract_name(self, raw_text: str, lines: Optional[List[str]] = None) -> Optional[str]:
        """Robust candidate name extractor handling initials (e.g. S.Kumar), prefixes, and filtering locations/titles."""
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

            # Normalize dotted initials without space: "S.Kumar" -> "S. Kumar"
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

        # Fallback: spaCy NER if available
        spacy_ents = self._extract_spacy_entities(raw_text)
        for ent_name in spacy_ents.get("PERSON", []):
            ent_clean = re.sub(r"[^a-zA-Z\s\.]", " ", ent_name).strip()
            words = ent_clean.split()
            if 1 <= len(words) <= 4:
                if not any(w.lower() in location_keywords or w.lower() in role_keywords for w in words):
                    return " ".join(words)

        return None

    def _extract_spacy_entities(self, text: str) -> dict:
        """Extract named entities using spaCy if available; return empty dict if unavailable or missing."""
        nlp = get_spacy_ner()
        if not nlp:
            return {"PERSON": [], "GPE": [], "ORG": []}
        try:
            doc = nlp(text[:10000])
            entities = {"PERSON": [], "GPE": [], "ORG": []}
            for ent in doc.ents:
                if ent.label_ in entities:
                    val = ent.text.strip()
                    if val and val not in entities[ent.label_]:
                        entities[ent.label_].append(val)
            return entities
        except Exception as e:
            logger.debug(f"spaCy NER extraction failed: {e}")
            return {"PERSON": [], "GPE": [], "ORG": []}

    def _extract_location(self, lines: List[str]) -> Optional[str]:
        """Extract location if present in top contact lines, with spaCy fallback."""
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

        # Fallback: spaCy GPE entities
        spacy_ents = self._extract_spacy_entities("\n".join(lines[:15]))
        for loc in spacy_ents.get("GPE", []):
            if loc and len(loc.split()) <= 4:
                return loc

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
        skills, other_terms, ignored_tokens, languages = self._extract_skills(raw_text, sections.get("skills", []))

        # 4. Experience Extraction
        experience = self._extract_experience(sections.get("experience", []))

        # 5. Education Extraction
        education = self._extract_education(raw_text, sections.get("education", []))

        # 6. Projects Extraction
        projects = self._extract_projects(sections.get("projects", []))

        # 7. Summary
        summary = " ".join(sections.get("summary", [])) if sections.get("summary") else None

        return ParsedResume(
            contact_info=contact_info,
            summary=summary,
            skills=skills,
            other_terms=other_terms,
            ignored_tokens=ignored_tokens,
            languages=languages,
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
        """Split document lines into logical resume sections with robust layout handling."""
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
        skill_indicator_headers = [
            "professional languages", "tools/frameworks", "databases",
            "professional skills", "computer skills", "core competencies"
        ]

        for i, line in enumerate(lines):
            line_clean = line.strip(" \t:#-=*~_#[]()|")
            line_lower = line_clean.lower()

            matched_section = None
            for sec, keywords in section_headers.items():
                for kw in keywords:
                    if line_lower == kw or line_lower.startswith(f"{kw}:"):
                        if line_clean.isupper() or line_clean.istitle() or line.endswith(":") or line.startswith(("#", "=", "-", "*", "~")):
                            # Avoid false match on lowercase wrapped tokens
                            if i > 0 and not lines[i - 1].strip().endswith((".", ":", ";")) and line_lower in ("skills", "experience") and not line_clean.isupper():
                                continue
                            matched_section = sec
                            break
                if matched_section:
                    break

            if matched_section:
                current_section = matched_section
                continue

            # Semantic redirection for lines misplaced by column/multi-column layout
            if (any(kw in line_lower for kw in skill_indicator_headers) or (len(extract_canonical_skills(line_clean)) >= 3 and len(line_clean.split()) <= 15)) and current_section != "projects":
                sections["skills"].append(line)
            elif any(kw in line_lower for kw in ["university", "college", "bachelor of", "b.tech", "relevant courses:"]) and current_section not in ("education", "experience", "skills"):
                sections["education"].append(line)
            else:
                sections[current_section].append(line)

        return sections

    def _extract_skills(
        self, full_text: str, skill_lines: List[str]
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Extract skills mapped strictly to the canonical taxonomy (with synonyms).
        Partitions tokens into:
          1. canonical_skills: matched to CANONICAL_SKILL_PATTERNS
          2. other_terms: unmapped terms kept for tracking but unused in matching
          3. ignored_tokens: years, degrees, institutions, headings, bullet sentences
          4. languages: natural / spoken languages
        """
        raw_candidates = set()

        for line in skill_lines:
            parts = re.split(r"[,|•·\n]", line)
            for part in parts:
                cleaned = part.strip()
                if cleaned and len(cleaned) < 50 and not any(ch in cleaned for ch in ["@", "http"]):
                    raw_candidates.add(cleaned)

        canonical_skills = set()
        other_terms = set()
        ignored_tokens = set()
        languages = set()

        # Extract spoken languages from full text
        for lang in extract_spoken_languages(full_text):
            languages.add(lang)

        # 1. Map extracted section tokens
        for token in raw_candidates:
            if token.lower() in SPOKEN_LANGUAGES:
                languages.add(token.capitalize())
                continue

            matched_canonical = extract_canonical_skills(token)
            if matched_canonical:
                canonical_skills.update(matched_canonical)
                continue

            other_terms.add(token)
            if is_ignored_token(token):
                ignored_tokens.add(token)

        # 2. Extract canonical skills from the full document text
        text_canonical = extract_canonical_skills(full_text)
        canonical_skills.update(text_canonical)

        return (
            sorted(list(canonical_skills)),
            sorted(list(other_terms)),
            sorted(list(ignored_tokens)),
            sorted(list(languages)),
        )

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

    def _extract_education(self, raw_text: str, edu_lines: List[str] = None) -> List[Education]:
        """Extract education entries scanning both edu_lines and raw_text for degree and institution patterns."""
        entries: List[Education] = []
        seen = set()
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        deg_regex = re.compile(
            r"\b(Bachelor(?:\s+of\s+[A-Za-z\s&]+)?|Master(?:\s+of\s+[A-Za-z\s&]+)?|B\.?Tech(?:-[A-Za-z\s&]+)?|B\.?E\.?|B\.?S\.?|M\.?Tech|M\.?S\.?|Ph\.?D\.?|HSC|SSLC)\b",
            re.IGNORECASE,
        )

        for i, line in enumerate(lines):
            m = deg_regex.search(line)
            if m:
                matched_str = m.group(0).strip()
                if line.strip().upper() in ["EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS"]:
                    continue

                deg = matched_str
                field = None
                if " in " in line.lower():
                    parts = re.split(r"\bin\b", line, flags=re.IGNORECASE)
                    deg = parts[0].strip()
                    field_part = parts[1].strip()
                    field = re.sub(r"\b20\d{2}.*$", "", field_part).strip(" -–")
                elif line.lower().startswith("b.tech-"):
                    parts = line.split("-", 1)
                    deg = parts[0].strip()
                    field = parts[1].strip()

                y_m = re.search(r"\b(20\d{2}\s*[-–]\s*20\d{2}|20\d{2})\b", line)
                grad_year = y_m.group(0).strip() if y_m else None

                inst = None
                for offset in [1, 2, -1]:
                    if 0 <= i + offset < len(lines):
                        cand = lines[i + offset]
                        if any(t in cand.lower() for t in ["university", "college", "institute", "school"]):
                            inst = cand.strip(" ,.")
                            break
                if not inst and any(t in line.lower() for t in ["university", "college", "institute", "school"]):
                    inst = line.strip(" ,.")

                key = (deg.lower(), (inst or "").lower())
                if key not in seen:
                    seen.add(key)
                    entries.append(Education(
                        institution=inst or "Unknown Institution",
                        degree=deg,
                        field_of_study=field,
                        graduation_year=grad_year,
                    ))

        # Fallback to checking edu_lines if none found
        if not entries and edu_lines:
            for line in edu_lines:
                if any(term in line.lower() for term in ["university", "college", "institute", "school", "bachelor", "master", "degree", "b.s", "m.s", "ph.d"]):
                    entries.append(Education(
                        institution=line,
                        degree=next((d for d in ["B.S.", "M.S.", "Ph.D.", "Bachelor", "Master", "B.Tech"] if d.lower() in line.lower()), None),
                    ))

        return entries

    def _extract_projects(self, proj_lines: List[str]) -> List[Project]:
        """Extract projects entries, cleanly capturing tech stacks and merging multi-line bullets."""
        projects: List[Project] = []
        if not proj_lines:
            return projects

        bullet_chars = ("-", "•", "*", "–", "·", "▪", "▫", "\u2022", "\u2023", "\u2043", "\u2219", "\ufffd")
        action_verbs = {
            "developed", "implemented", "applied", "designed", "improved",
            "optimised", "optimized", "created", "explored", "focused", "built", "led", "analyzed"
        }
        current_project: Optional[Project] = None

        for raw_line in proj_lines:
            line = raw_line.strip()
            if not line:
                continue

            line_clean = re.sub(r"^[\s\-•*–·▪▫\u2022\u2023\u2043\u2219\ufffd]+", "", line).strip()
            skills_in_line = extract_canonical_skills(line_clean)
            is_tech_line = bool(skills_in_line) and len(line_clean.split()) <= 6 and not any(line_clean.lower().startswith(v) for v in action_verbs)
            starts_bullet = any(line.startswith(c) for c in bullet_chars)
            is_action_sentence = any(line_clean.lower().startswith(v) for v in action_verbs)
            is_description = (
                starts_bullet
                or is_action_sentence
                or line_clean.endswith(".")
                or line_clean[0].islower()
                or len(line_clean.split()) > 7
            )

            if current_project and is_tech_line and not current_project.technologies:
                current_project.technologies = skills_in_line
            elif current_project and is_description:
                if current_project.description:
                    current_project.description += " " + line_clean
                else:
                    current_project.description = line_clean
            else:
                if len(line_clean) < 80 and not line_clean.lower().startswith(("relevant courses", "bachelor", "vel tech", "projects", "education")):
                    current_project = Project(name=line_clean, description="", technologies=[])
                    projects.append(current_project)

        return projects


def safe_merge_parsed_data(existing_pd: Optional[dict], new_pd: dict) -> dict:
    """
    Safely merges new parsed resume data into existing parsed data.
    Guarantees that non-empty critical fields (education, contact_info, skills, projects)
    are never wiped out or replaced by empty lists/dicts due to incomplete extraction.
    """
    if not existing_pd:
        return new_pd

    merged = dict(existing_pd)
    # Merge contact info
    existing_ci = existing_pd.get("contact_info") or {}
    new_ci = new_pd.get("contact_info") or {}
    merged_ci = dict(existing_ci)
    for k, v in new_ci.items():
        if v and not merged_ci.get(k):
            merged_ci[k] = v
    merged["contact_info"] = merged_ci

    # Skills: union of skills
    existing_skills = set(existing_pd.get("skills") or [])
    new_skills = set(new_pd.get("skills") or [])
    merged["skills"] = sorted(list(existing_skills | new_skills))

    # Education: preserve existing if new is empty
    new_edu = new_pd.get("education") or []
    if new_edu:
        merged["education"] = new_edu
    elif not merged.get("education"):
        merged["education"] = []

    # Projects: preserve existing if new is empty
    new_proj = new_pd.get("projects") or []
    if new_proj:
        merged["projects"] = new_proj
    elif not merged.get("projects"):
        merged["projects"] = []

    # Experience: preserve existing if new is empty
    new_exp = new_pd.get("experience") or []
    if new_exp:
        merged["experience"] = new_exp

    # Certifications: preserve existing if new is empty
    new_certs = new_pd.get("certifications") or []
    if new_certs:
        merged["certifications"] = new_certs

    # Other terms, ignored tokens, languages
    for field in ("other_terms", "ignored_tokens", "languages"):
        existing_items = set(existing_pd.get(field) or [])
        new_items = set(new_pd.get(field) or [])
        merged[field] = sorted(list(existing_items | new_items))

    # Summary
    if new_pd.get("summary"):
        merged["summary"] = new_pd["summary"]

    return merged


parser_agent = ParserAgent()
