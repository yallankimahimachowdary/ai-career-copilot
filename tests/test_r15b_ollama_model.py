import json
from pathlib import Path
import pytest

from app.core.config import settings


def test_llm_arms_logged_model_matches_configured_model():
    """Verify that any LLM ranking arm logged model strictly matches configured settings."""
    configured_ollama_model = settings.OLLAMA_MODEL
    configured_gemini_model = settings.GEMINI_MODEL

    assert configured_ollama_model == "llama3.2:3b", (
        f"Configured Ollama model must be llama3.2:3b, got {configured_ollama_model}"
    )
    assert configured_gemini_model == "gemini-3.5-flash-lite", (
        f"Configured Gemini model must be gemini-3.5-flash-lite, got {configured_gemini_model}"
    )

    ranking_files = list(Path("results/dryrun/phase_b_ranking").glob("*.json"))
    assert len(ranking_files) > 0, "No ranking files found to audit"

    for rf in ranking_files:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        out_meta = data.get("outputs", {}).get("run_metadata", {})
        prov = data.get("provenance", {})

        logged_model = out_meta.get("model") or prov.get("returned_model")
        if not logged_model or logged_model == "n/a":
            continue

        if "ollama" in rf.name or out_meta.get("provider") == "ollama":
            assert logged_model == configured_ollama_model, (
                f"File {rf} logged Ollama model '{logged_model}', which diverges from configured model '{configured_ollama_model}'"
            )
        elif "gemini" in rf.name or out_meta.get("provider") == "gemini":
            assert logged_model == configured_gemini_model, (
                f"File {rf} logged Gemini model '{logged_model}', which diverges from configured model '{configured_gemini_model}'"
            )
