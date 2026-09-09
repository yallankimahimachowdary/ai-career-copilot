import hashlib
import math
from typing import List
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.schemas.resume import ParsedResume


class EmbeddingService:
    """Service to compute dense semantic embeddings for resumes."""

    def __init__(self):
        self.dimension = settings.EMBEDDING_DIMENSION
        self.openai_key = settings.OPENAI_API_KEY

    def construct_embed_text(self, parsed: ParsedResume) -> str:
        """Combine relevant parsed fields into rich text for semantic embedding."""
        parts = []
        if parsed.contact_info.name:
            parts.append(f"Candidate: {parsed.contact_info.name}")
        if parsed.summary:
            parts.append(f"Summary: {parsed.summary}")
        if parsed.skills:
            parts.append(f"Skills: {', '.join(parsed.skills)}")
        for exp in parsed.experience:
            desc = " ".join(exp.description)
            parts.append(f"Role: {exp.title} at {exp.company}. {desc}")
        for edu in parsed.education:
            parts.append(f"Education: {edu.institution} {edu.degree or ''}")

        return "\n".join(parts)

    def construct_job_embed_text(
        self,
        title: str,
        description: str,
        skills: List[str] | None = None,
        company: str = "",
        location: str = "",
    ) -> str:
        """Combine relevant job posting fields into rich text for semantic embedding."""
        parts = []
        if title:
            parts.append(f"Job Title: {title}")
        if company:
            parts.append(f"Company: {company}")
        if location:
            parts.append(f"Location: {location}")
        if skills:
            parts.append(f"Required Skills: {', '.join(skills)}")
        if description:
            # Cap description to avoid exceeding embedding model context limits
            parts.append(f"Description: {description[:4000]}")
        return "\n".join(parts)

    async def get_embedding(self, text: str) -> List[float]:
        """Generate a dense vector embedding for input text."""
        if self.openai_key:
            try:
                return await self._get_openai_embedding(text)
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed: {e}. Trying alternative provider.")

        if settings.GEMINI_API_KEY:
            try:
                return await self._get_gemini_embedding(text)
            except Exception as e:
                logger.warning(f"Gemini embedding call failed: {e}. Falling back to local vector generator.")

        return self._generate_deterministic_vector(text)

    async def _get_gemini_embedding(self, text: str) -> List[float]:
        """Fetch 1536-dim embedding from Google Gemini gemini-embedding-001."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text[:8000]}]},
            "outputDimensionality": self.dimension,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            vals = data["embedding"]["values"]
            norm = math.sqrt(sum(x * x for x in vals))
            if norm > 0:
                return [x / norm for x in vals]
            return vals



    async def _get_openai_embedding(self, text: str) -> List[float]:
        """Fetch embedding from OpenAI text-embedding-3-small."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "text-embedding-3-small",
                "input": text[:8000],  # Stay within context limit
                "dimensions": self.dimension,
            }
            response = await client.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    def _generate_deterministic_vector(self, text: str) -> List[float]:
        """Generate a unit-normalized deterministic vector of length `self.dimension`.
        
        Uses cryptographic hash chunks of the text to seed float values, ensuring that:
        1. The vector has exact dimension `self.dimension`.
        2. Identical text produces identical vectors.
        3. The vector is L2-normalized (magnitude == 1.0) for valid cosine distance.
        """
        raw_values = []
        text_bytes = text.encode("utf-8")

        # Generate enough pseudorandom float values using sequential sha256 chunks
        for i in range(self.dimension):
            h = hashlib.sha256(text_bytes + str(i).encode("utf-8")).digest()
            # Unpack first 4 bytes as unsigned int
            int_val = int.from_bytes(h[:4], "big")
            # Map to range [-1.0, 1.0]
            val = (int_val / (2**32 - 1)) * 2.0 - 1.0
            raw_values.append(val)

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in raw_values))
        if norm > 0:
            return [x / norm for x in raw_values]
        return [0.0] * self.dimension


embedding_service = EmbeddingService()
