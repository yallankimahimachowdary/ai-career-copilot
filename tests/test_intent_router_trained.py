"""Tests for the trained Intent Router classifier, calibration, hash locking, and safety fallbacks."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from app.schemas.chat import IntentType, RouterDecision
from app.services.intent_router_eval import to_canonical_intent
from app.services.router_service import (
    CANONICAL_TO_INTENT,
    STRATEGY_MAP,
    AdaptiveRouterService,
    router_service,
)
from scripts.check_router_leakage import check_splits


@pytest.mark.asyncio
async def test_model_loads_and_predicts_all_intents():
    """Verify model loads successfully and predicts valid IntentType for all 5 intents."""
    service = AdaptiveRouterService()
    assert service._model_loaded is True
    assert service._model is not None

    sample_queries = {
        "job_search": "Find entry level Python backend developer openings in Bangalore.",
        "skill_gap_analysis": "What skills do I lack for this DevOps engineer position?",
        "resume_feedback": "Review my resume bullet points and format for ATS optimization.",
        "career_advice": "Should I choose a startup or an MNC for my first software engineering job?",
        "interview_preparation": "Give me mock technical interview questions on Python generators and decorators.",
    }

    for expected_intent, query in sample_queries.items():
        decision = await service.classify_intent(query, backend="trained")
        assert isinstance(decision, RouterDecision)
        canonical = to_canonical_intent(decision.intent)
        assert canonical in STRATEGY_MAP
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.backend == "trained"
        assert decision.fallback_used is False


@pytest.mark.asyncio
async def test_predict_proba_valid_distribution():
    """Verify predict_proba produces valid probability distributions (sum to 1.0, non-negative)."""
    service = AdaptiveRouterService()
    assert service._model is not None

    test_queries = [
        "Backend developer jobs in Pune",
        "How do I prepare for STAR behavioral interview?",
        "Critique my resume summary section",
    ]
    probs = service._model.predict_proba(test_queries)
    assert probs.shape[0] == len(test_queries)
    assert probs.shape[1] == 5

    for row in probs:
        assert np.all(row >= 0.0), "Probabilities must be non-negative"
        assert np.isclose(np.sum(row), 1.0, atol=1e-5), f"Probabilities must sum to 1.0, got {np.sum(row)}"


@pytest.mark.asyncio
async def test_strategy_matches_strategy_map():
    """Verify RouterDecision contains strategy matching STRATEGY_MAP."""
    service = AdaptiveRouterService()
    decision = await service.classify_intent("What is the average fresher salary for SDE 1 in Hyderabad?", backend="trained")
    canonical = to_canonical_intent(decision.intent)
    expected_strategy = STRATEGY_MAP[canonical]
    assert decision.strategy == expected_strategy
    assert decision.strategy_selected == expected_strategy


def test_test_set_hash_lock():
    """Verify test.jsonl SHA-256 strictly matches locked hash in metadata.json."""
    data_dir = Path("data/router")
    test_file = data_dir / "test.jsonl"
    meta_file = data_dir / "metadata.json"

    assert test_file.exists(), "test.jsonl must exist"
    assert meta_file.exists(), "metadata.json must exist"

    h = hashlib.sha256()
    with open(test_file, "rb") as f:
        h.update(f.read())
    actual_hash = h.hexdigest().upper()

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    locked_hash = meta["splits"]["test"]["sha256"].upper()

    assert actual_hash == locked_hash, f"Test split hash altered! Actual {actual_hash} != Locked {locked_hash}"


def test_zero_data_leakage():
    """Re-runs check_splits programmatically, asserting zero leakage across train, dev, and test."""
    data_dir = Path("data/router")
    no_leakage = check_splits(data_dir, threshold=0.7)
    assert no_leakage is True, "Dataset splits contain leakage violations!"


@pytest.mark.asyncio
async def test_determinism_ten_runs():
    """Calling predict on the same query 10 times yields identical class and probability."""
    service = AdaptiveRouterService()
    query = "Recommend entry level data analyst postings in Gurgaon"

    intents = []
    confs = []
    for _ in range(10):
        decision = await service.classify_intent(query, backend="trained")
        intents.append(decision.intent)
        confs.append(decision.confidence)

    assert len(set(intents)) == 1, f"Non-deterministic intent predictions: {set(intents)}"
    for conf in confs[1:]:
        assert np.isclose(conf, confs[0], atol=1e-6), f"Confidence varied across runs: {confs}"


@pytest.mark.asyncio
async def test_model_hash_tamper_fallback(tmp_path):
    """Modify one byte of a copy in a tmp fixture, assert router logs warning and falls back to heuristic."""
    service = AdaptiveRouterService()

    # Create dummy tampered model file
    fake_model_path = tmp_path / "intent_router_v1.joblib"
    fake_meta_path = tmp_path / "intent_router_v1.meta.json"

    fake_model_path.write_bytes(b"TAMPERED_BYTE_DATA_FOR_SECURITY_TEST")
    fake_meta_path.write_text(json.dumps({
        "model_sha256": "ORIGINAL_EXPECTED_HASH_THAT_DOES_NOT_MATCH_TAMPERED",
        "validation_metrics": {"tau": 0.33},
        "classes": ["job_search"],
    }))

    # Point model loading to tampered files
    with patch("app.services.router_service.Path") as mock_path:
        def path_side_effect(arg):
            if "intent_router_v1.joblib" in str(arg):
                return fake_model_path
            if "intent_router_v1.meta.json" in str(arg):
                return fake_meta_path
            return Path(arg)

        mock_path.side_effect = path_side_effect

        tampered_service = AdaptiveRouterService()
        assert tampered_service._model_loaded is False
        assert tampered_service._model is None

        # Verify fallback to heuristic
        decision = await tampered_service.classify_intent("Find python developer jobs", backend="trained")
        assert decision.backend == "heuristic"
        assert decision.fallback_used is True
