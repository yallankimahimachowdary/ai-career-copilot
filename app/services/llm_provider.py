"""Unified LLM Provider Layer supporting Ollama and Gemini with structured JSON output and detailed audit logging."""

import abc
from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


class LLMResponse:
    """Standardized response from an LLM call."""

    def __init__(
        self,
        raw_text: str,
        parsed_json: Dict[str, Any],
        provider: str,
        model: str,
        temperature: float,
        max_tokens: int,
        latency_ms: float,
        timestamp: str,
    ):
        self.raw_text = raw_text
        self.data = parsed_json
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.latency_ms = latency_ms
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "data": self.data,
            "raw_text": self.raw_text,
        }


def clean_and_parse_json(text_content: str) -> Dict[str, Any]:
    """Robust JSON parser that strips markdown fences and repairs minor truncation."""
    cleaned = text_content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start_idx = cleaned.find("{")
    if start_idx != -1:
        candidate = cleaned[start_idx:]
        candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")
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
            return json.loads(fixed)

    raise ValueError(f"Could not extract valid JSON from response: {text_content[:200]}")


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM generation."""

    @abc.abstractmethod
    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        **kwargs: Any,
    ) -> LLMResponse:
        pass


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider with keep_alive and token limiting."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        keep_alive: str = "30m",
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": keep_alive,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data.get("response", "")

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        ts = datetime.now(timezone.utc).isoformat()
        parsed = clean_and_parse_json(raw_text)

        logger.info(
            f"[LLM Call] provider=ollama model={self.model} temp={temperature} "
            f"max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
        )

        return LLMResponse(
            raw_text=raw_text,
            parsed_json=parsed,
            provider="ollama",
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            latency_ms=latency_ms,
            timestamp=ts,
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider reading keys strictly from environment."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Read API key strictly from environment variable or settings
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        self.model = model or os.environ.get("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        timeout: float = 30.0,
        mock_response: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        ts = datetime.now(timezone.utc).isoformat()

        require_api_key: bool = kwargs.get("require_api_key", False)

        # If key is missing and strict key presence is required, raise error
        if not self.api_key and require_api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not configured.")

        # Mock fallback if key is not available or mock_response is provided
        if not self.api_key or mock_response is not None:
            time.sleep(0.05)  # Simulate small network roundtrip
            data = mock_response or {
                "status": "success",
                "provider": "gemini-mock",
                "summary": "Mocked Gemini structured evaluation response.",
                "analysis": {"fit_score": 85, "recommendations": ["Review architecture guidelines."]},
            }
            raw_text = json.dumps(data)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(
                f"[LLM Call] provider=gemini-mock model={self.model} temp={temperature} "
                f"max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
            )
            return LLMResponse(
                raw_text=raw_text,
                parsed_json=data,
                provider="gemini-mock",
                model=f"{self.model}-mock",
                temperature=temperature,
                max_tokens=max_tokens,
                latency_ms=latency_ms,
                timestamp=ts,
            )


        model_clean = self.model.removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            res_json = resp.json()
            raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        parsed = clean_and_parse_json(raw_text)

        logger.info(
            f"[LLM Call] provider=gemini model={self.model} temp={temperature} "
            f"max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
        )

        return LLMResponse(
            raw_text=raw_text,
            parsed_json=parsed,
            provider="gemini",
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            latency_ms=latency_ms,
            timestamp=ts,
        )


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """Factory to retrieve configured LLM provider instance."""
    name = (provider_name or getattr(settings, "LLM_PROVIDER", "ollama")).lower().strip()
    if name == "gemini":
        return GeminiProvider()
    return OllamaProvider()
