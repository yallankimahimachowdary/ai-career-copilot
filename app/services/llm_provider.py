"""Unified LLM Provider Layer supporting Ollama and Gemini with structured JSON output and detailed audit logging."""

import abc
from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
import asyncio
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
        requested_model: Optional[str] = None,
        answered_model: Optional[str] = None,
        seed_requested: Optional[int] = None,
        seed_sent: Optional[int] = None,
        seed_applied: Optional[int] = None,
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        quantization: str = "n/a",
    ):
        self.raw_text = raw_text
        self.data = parsed_json
        self.provider = provider
        self.model = model
        self.requested_model = requested_model or model
        self.answered_model = answered_model or model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.latency_ms = latency_ms
        self.timestamp = timestamp
        self.seed_requested = seed_requested
        self.seed_sent = seed_sent if seed_sent is not None else seed_requested
        self.seed_applied = seed_applied
        self.prompt_tokens = prompt_tokens
        self.response_tokens = response_tokens
        self.quantization = quantization

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "requested_model": self.requested_model,
            "answered_model": self.answered_model,
            "quantization": self.quantization,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed_requested": self.seed_requested,
            "seed_sent": self.seed_sent,
            "seed_applied": self.seed_applied,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
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

    # Try json-repair if json.loads failed
    try:
        import json_repair
        return json_repair.loads(cleaned)
    except Exception:
        pass

    start_idx = cleaned.find("{")
    if start_idx != -1:
        candidate = cleaned[start_idx:]
        candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Try recovering individually closed objects if it's a list or dictionary
        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")
        repaired = re.sub(r',\s*"[^"]*"?\s*$', '', candidate)
        repaired = re.sub(r',\s*$', '', repaired)
        repaired += ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # Regex find all object items if ranked_jobs structure is present
    item_matches = re.findall(r'\{\s*"job_id"\s*:\s*"([^"]+)"[^}]*\}', cleaned)
    if item_matches:
        recovered_items = []
        for obj_str in re.finditer(r'\{[^{}]*"job_id"[^{}]*\}', cleaned):
            try:
                rec_obj = json.loads(obj_str.group(0))
                recovered_items.append(rec_obj)
            except Exception:
                # Regex extract individual keys
                m_id = re.search(r'"job_id"\s*:\s*"([^"]+)"', obj_str.group(0))
                if m_id:
                    recovered_items.append({
                        "job_id": m_id.group(1),
                        "rank": len(recovered_items) + 1,
                        "matched_skills": [],
                        "missing_skills": [],
                        "reason": "Recovered from partial JSON.",
                    })
        if recovered_items:
            return {"ranked_jobs": recovered_items}

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
        seed: Optional[int] = 42,
        keep_alive: str = "30m",
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        url = f"{self.base_url}/api/generate"
        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_thread": int(kwargs.get("num_thread", 4)),
        }
        if seed is not None:
            options["seed"] = int(seed)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": options,
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

        seed_requested = seed
        seed_sent = seed if seed is not None else None
        seed_applied = data.get("seed") or None
        prompt_tokens = data.get("prompt_eval_count", 0)
        response_tokens = data.get("eval_count", 0)
        quantization = "Q4_K_M" if "llama" in self.model.lower() else "n/a"

        logger.info(
            f"[LLM Call] provider=ollama model={self.model} seed_requested={seed_requested} seed_sent={seed_sent} seed_applied={seed_applied} "
            f"prompt_tokens={prompt_tokens} response_tokens={response_tokens} quantization={quantization} "
            f"temp={temperature} max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
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
            seed_requested=seed_requested,
            seed_sent=seed_sent,
            seed_applied=seed_applied,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            quantization=quantization,
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider reading keys strictly from environment."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Read API key strictly from environment variable or settings
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        self.model = model or os.environ.get("GEMINI_MODEL") or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        seed: Optional[int] = 42,
        timeout: float = 30.0,
        mock_response: Optional[Dict[str, Any]] = None,
        experiment_mode: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        ts = datetime.now(timezone.utc).isoformat()
        requested_model = self.model

        require_api_key: bool = kwargs.get("require_api_key", False) or experiment_mode

        # If in experiment mode, strictly prohibit mock fallback and require API key
        if experiment_mode and mock_response is not None:
            raise RuntimeError("Mock provider responses are strictly prohibited in experiment mode.")
        if experiment_mode and not self.api_key:
            raise RuntimeError(f"Experiment mode requires a valid GEMINI_API_KEY for model '{requested_model}'.")

        if not self.api_key and require_api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not configured.")

        # Mock fallback only when NOT in experiment mode and (no key or mock_response is provided)
        if not experiment_mode and (not self.api_key or mock_response is not None):
            time.sleep(0.05)  # Simulate small network roundtrip
            data = mock_response or {
                "status": "success",
                "provider": "gemini-mock",
                "summary": "Mocked Gemini structured evaluation response.",
                "analysis": {"fit_score": 85, "recommendations": ["Review architecture guidelines."]},
            }
            raw_text = json.dumps(data)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            seed_requested = seed
            seed_sent = None
            seed_applied = None
            prompt_tokens = len(prompt.split())
            response_tokens = len(raw_text.split())
            quantization = "mock"
            logger.info(
                f"[LLM Call] provider=gemini-mock requested_model={requested_model} answered_model={requested_model}-mock "
                f"seed_requested={seed_requested} seed_sent={seed_sent} seed_applied={seed_applied} "
                f"prompt_tokens={prompt_tokens} response_tokens={response_tokens} quantization={quantization} "
                f"temp={temperature} max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
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
                requested_model=requested_model,
                answered_model=f"{requested_model}-mock",
                seed_requested=seed_requested,
                seed_sent=seed_sent,
                seed_applied=seed_applied,
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                quantization=quantization,
            )

        model_clean = self.model.removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        seed_requested = seed
        seed_sent = int(seed) if seed is not None else None

        gen_config: Dict[str, Any] = {
            "response_mime_type": "application/json",
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if seed_sent is not None:
            gen_config["seed"] = seed_sent

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }

        # Client-side rate-limiting delay between calls to mitigate 429 quota exhaustion
        await asyncio.sleep(1.0)

        # Retries with exponential backoff for 429 and 503 (at least 5 attempts)
        max_http_attempts = 5
        base_backoff = 2.0
        resp = None
        last_http_err = None

        for attempt in range(1, max_http_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code in (429, 503) and attempt < max_http_attempts:
                        retry_after = resp.headers.get("retry-after")
                        if retry_after:
                            try:
                                backoff = float(retry_after)
                            except ValueError:
                                backoff = base_backoff * (2 ** (attempt - 1))
                        else:
                            backoff = base_backoff * (2 ** (attempt - 1))
                        logger.warning(
                            f"[Gemini Retry] Status {resp.status_code} on attempt {attempt}/{max_http_attempts} for model '{requested_model}'. Backing off {backoff:.1f}s..."
                        )
                        await asyncio.sleep(backoff)
                        continue
                    resp.raise_for_status()
                    break
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_http_err = exc
                if attempt < max_http_attempts:
                    backoff = base_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        f"[Gemini Retry] Exception {type(exc).__name__} on attempt {attempt}/{max_http_attempts} for model '{requested_model}'. Backing off {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue
                else:
                    # Sanitize message to ensure key never appears
                    safe_msg = f"{type(exc).__name__}: HTTP error on model '{requested_model}' after {max_http_attempts} attempts."
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                        safe_msg += f" Status code: {exc.response.status_code}"
                    logger.error(safe_msg)
                    raise RuntimeError(safe_msg) from None

        if resp is None:
            raise RuntimeError(f"Gemini call failed after {max_http_attempts} attempts: {last_http_err}")

        res_json = resp.json()
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        answered_model = res_json.get("modelVersion") or self.model
        usage = res_json.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        response_tokens = usage.get("candidatesTokenCount", 0)
        # Honest provider metadata: check if remote API explicitly returned/verified seed
        seed_applied = res_json.get("seed") or res_json.get("usageMetadata", {}).get("seed") or None
        quantization = kwargs.get("quantization", None)

        # Pinned model enforcement in experiment mode (supports Google API canonical aliases)
        if experiment_mode and requested_model:
            req_clean = requested_model.removeprefix("models/").lower()
            ans_clean = answered_model.removeprefix("models/").lower()
            known_aliases = {
                "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
                "gemini-3.5-flash": "gemini-3.6-flash",
                "gemini-2.0-flash": "gemini-2.0-flash",
                "gemini-1.5-flash": "gemini-1.5-flash",
            }
            is_match = (
                req_clean == ans_clean
                or ans_clean.startswith(req_clean)
                or req_clean.startswith(ans_clean)
                or known_aliases.get(req_clean) == ans_clean
                or known_aliases.get(req_clean, "").startswith(ans_clean)
                or ans_clean.startswith(known_aliases.get(req_clean, "___"))
            )
            if not is_match:
                raise RuntimeError(
                    f"Gemini model mismatch in experiment mode: requested '{requested_model}' but answered '{answered_model}'."
                )

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        parsed = clean_and_parse_json(raw_text)

        logger.info(
            f"[LLM Call] provider=gemini requested_model={requested_model} answered_model={answered_model} "
            f"seed_requested={seed_requested} seed_sent={seed_sent} seed_applied={seed_applied} "
            f"prompt_tokens={prompt_tokens} response_tokens={response_tokens} quantization={quantization} "
            f"temp={temperature} max_tokens={max_tokens} latency_ms={latency_ms} timestamp={ts}"
        )

        return LLMResponse(
            raw_text=raw_text,
            parsed_json=parsed,
            provider="gemini",
            model=answered_model,
            temperature=temperature,
            max_tokens=max_tokens,
            latency_ms=latency_ms,
            timestamp=ts,
            requested_model=requested_model,
            answered_model=answered_model,
            seed_requested=seed_requested,
            seed_sent=seed_sent,
            seed_applied=seed_applied,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            quantization=quantization,
        )


def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """Factory to retrieve configured LLM provider instance."""
    name = (provider_name or getattr(settings, "LLM_PROVIDER", "ollama")).lower().strip()
    if name == "gemini":
        return GeminiProvider()
    return OllamaProvider()
