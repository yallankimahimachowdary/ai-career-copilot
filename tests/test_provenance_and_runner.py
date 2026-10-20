"""Unit tests for R9-3 (Provenance Logging) and R9-4 (Runner Fixes).

Tests:
1. Full provenance generation & validation (all required fields present)
2. Rejection of runs missing provenance fields
3. Model alias mismatch detection (gemini-3.5-flash vs gemini-3.6-flash) & strict failure
4. Resumable batch runner producing byte-identical output after simulated mid-run crash
5. No silent fallback: worker/LLM exceptions recorded as explicit FAILURE rows
"""

import asyncio
from pathlib import Path
import pytest

from app.core.provenance import (
    ModelAliasMismatchError,
    ProvenanceValidationError,
    build_provenance_record,
    validate_provenance_payload,
)
from scripts.experiment_runner import BatchRunner, ExperimentLogger


def test_provenance_full_record_generation():
    """Build provenance record and verify all required keys are present and valid."""
    record = build_provenance_record(
        requested_model="gemini-2.5-flash",
        returned_model="models/gemini-2.5-flash",
        seed=42,
        run_type="dryrun",
        snapshot_hash="SNAP_ABC_123",
        gate_flags={"seniority_gate": True},
        strict_model_match=True,
    )

    assert "git_commit_hash" in record
    assert "config_hash" in record
    assert "snapshot_hash" in record
    assert record["snapshot_hash"] == "SNAP_ABC_123"
    assert record["seed"] == 42
    assert record["requested_model"] == "gemini-2.5-flash"
    assert record["returned_model"] == "models/gemini-2.5-flash"
    assert record["run_type"] == "dryrun"
    assert "timestamp" in record
    assert record["gate_flags"]["seniority_gate"] is True
    assert record["model_alias_mismatch"] is False

    # Validating the generated record must pass
    assert validate_provenance_payload(record, strict_model_match=True) is True


def test_provenance_rejection_missing_fields():
    """A run missing any required provenance field is rejected."""
    incomplete_record = {
        "git_commit_hash": "abc1234",
        "config_hash": "cfg1234",
        # missing snapshot_hash
        "seed": 42,
        "requested_model": "test-model",
        "returned_model": "test-model",
        "gate_flags": {},
        "run_type": "dryrun",
        "timestamp": "2026-10-20T00:00:00Z",
    }
    with pytest.raises(ProvenanceValidationError):
        validate_provenance_payload(incomplete_record)

    # Empty string field is also rejected
    incomplete_record["snapshot_hash"] = "   "
    with pytest.raises(ProvenanceValidationError):
        validate_provenance_payload(incomplete_record)


def test_provenance_model_alias_mismatch_strict_failure():
    """Requested vs returned model alias mismatch is recorded and fails the run in strict mode."""
    # Mismatch in strict mode -> must raise ModelAliasMismatchError
    with pytest.raises(ModelAliasMismatchError):
        build_provenance_record(
            requested_model="gemini-3.5-flash",
            returned_model="gemini-3.6-flash",
            seed=42,
            run_type="dryrun",
            strict_model_match=True,
        )

    # In non-strict mode, mismatch is flagged but does not fail
    record = build_provenance_record(
        requested_model="gemini-3.5-flash",
        returned_model="gemini-3.6-flash",
        seed=42,
        run_type="dryrun",
        strict_model_match=False,
    )
    assert record["model_alias_mismatch"] is True
    assert record["requested_model"] == "gemini-3.5-flash"
    assert record["returned_model"] == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_resumable_runner_byte_identical_output(tmp_path: Path):
    """Resuming a batch run after a kill produces byte-identical output to an uninterrupted run."""
    items = [
        {"id": f"item_{i:02d}", "prompt": f"test_prompt_{i}", "val": i * 10}
        for i in range(10)
    ]

    async def mock_worker(item):
        return {"result": f"processed_{item['id']}", "calc": item["val"] * 2}

    # 1. Uninterrupted run
    dir_uninterrupted = tmp_path / "uninterrupted"
    runner_full = BatchRunner(
        experiment_name="batch_test",
        base_dir=dir_uninterrupted,
        deterministic_mode=True,
    )
    stats_full = await runner_full.run_batch(items, mock_worker)
    assert stats_full["processed"] == 10
    compiled_full = runner_full.logger.compile_results()
    full_bytes = compiled_full.read_bytes()

    # 2. Interrupted run: kill after 4 items
    dir_interrupted = tmp_path / "interrupted"
    runner_interrupted = BatchRunner(
        experiment_name="batch_test",
        base_dir=dir_interrupted,
        deterministic_mode=True,
    )
    with pytest.raises(KeyboardInterrupt):
        await runner_interrupted.run_batch(items, mock_worker, simulate_crash_at=4)

    # Verify only 4 items were processed prior to crash
    assert len(list((dir_interrupted / "batch_test").glob("item_*.json"))) == 4

    # 3. Resume the interrupted run
    runner_resumed = BatchRunner(
        experiment_name="batch_test",
        base_dir=dir_interrupted,
        deterministic_mode=True,
    )
    stats_resumed = await runner_resumed.run_batch(items, mock_worker)
    assert stats_resumed["skipped"] == 4
    assert stats_resumed["processed"] == 6

    compiled_resumed = runner_resumed.logger.compile_results()
    resumed_bytes = compiled_resumed.read_bytes()

    # Byte-identical assertion
    assert full_bytes == resumed_bytes, "Compiled output after resume is not byte-identical to uninterrupted run!"


@pytest.mark.asyncio
async def test_no_silent_fallback_on_llm_failure(tmp_path: Path):
    """An LLM failure must be recorded as a FAILURE row, never as a result or completed row."""
    items = [
        {"id": "item_ok", "prompt": "normal request"},
        {"id": "item_err", "prompt": "trigger rate limit exception"},
    ]

    async def flaky_worker(item):
        if "err" in item["id"]:
            raise RuntimeError("Gemini 429 QuotaExceededError")
        return {"result": "success"}

    runner = BatchRunner(
        experiment_name="fallback_test",
        base_dir=tmp_path,
        deterministic_mode=True,
    )

    stats = await runner.run_batch(items, flaky_worker)
    assert stats["processed"] == 1
    assert stats["failed"] == 1

    # Inspect the error log file
    err_file = tmp_path / "fallback_test" / "item_err.json"
    assert err_file.exists()
    import json
    with open(err_file, "r", encoding="utf-8") as f:
        err_data = json.load(f)

    # Must be recorded as FAILURE, never completed or mock result
    assert err_data["status"] == "FAILURE"
    assert "Gemini 429" in err_data.get("error", "")
    assert err_data["outputs"]["status"] == "FAILURE"
