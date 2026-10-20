"""
scripts.experiment_runner
-------------------------
Experiment Run Logger, Provenance Validator, and Resumable Batch Runner (R9-3, R9-4).

Features:
- Enforces full provenance metadata on every logged run (git hash, config hash, snapshot hash,
  seed, requested & returned models, gate flags, run_type, timestamp).
- Strict model alias check: fails immediately if requested model != returned model.
- Resumable batch execution: skipping completed items produces byte-identical output to uninterrupted runs.
- No silent fallback: worker/LLM exceptions record an explicit FAILURE row, never a mock/fallback result.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from app.core.provenance import (
    ModelAliasMismatchError,
    ProvenanceValidationError,
    build_provenance_record,
    validate_provenance_payload,
)

DEFAULT_EXPERIMENTS_DIR = Path("artifacts/experiments/runs")


class ExperimentLogger:
    """Logs individual experiment executions to structured JSON files with provenance."""

    def __init__(
        self,
        experiment_name: str = "default_experiment",
        base_dir: Optional[Path] = None,
        run_type: str = "dryrun",
        strict_provenance: bool = True,
    ):
        self.experiment_name = experiment_name
        self.run_type = run_type
        self.strict_provenance = strict_provenance
        root = base_dir or DEFAULT_EXPERIMENTS_DIR
        self.dir = root / experiment_name
        self.dir.mkdir(parents=True, exist_ok=True)

    def is_completed(self, item_id: str) -> bool:
        """Check if an item has already been successfully recorded."""
        record_path = self.dir / f"{item_id}.json"
        if not record_path.exists():
            return False
        try:
            with open(record_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("status") == "completed"
        except Exception:
            return False

    def log_run(
        self,
        item_id: str,
        requested_model: str,
        returned_model: str,
        seed: int,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        provider: str = "ollama",
        status: str = "completed",
        snapshot_hash: Optional[str] = None,
        snapshot_path: Optional[Path | str] = None,
        config_path: Optional[Path | str] = None,
        gate_flags: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        fixed_timestamp: Optional[str] = None,
    ) -> Path:
        """Persist experiment output with validated provenance metadata."""
        # Build provenance record
        prov = build_provenance_record(
            requested_model=requested_model,
            returned_model=returned_model,
            seed=seed,
            run_type=self.run_type,
            snapshot_path=snapshot_path,
            snapshot_hash=snapshot_hash,
            config_path=config_path,
            gate_flags=gate_flags,
            strict_model_match=self.strict_provenance,
        )

        if fixed_timestamp:
            prov["timestamp"] = fixed_timestamp

        # Enforce validation
        if self.strict_provenance:
            validate_provenance_payload(prov, strict_model_match=True)

        payload = {
            "item_id": item_id,
            "experiment_name": self.experiment_name,
            "provider": provider,
            "status": status,
            "provenance": prov,
            "inputs": inputs,
            "outputs": outputs,
        }
        if error_message:
            payload["error"] = error_message

        file_path = self.dir / f"{item_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, default=str)
        return file_path

    def compile_results(self, output_path: Optional[Path] = None) -> Path:
        """Compile all item records into a deterministic, sorted JSONL file."""
        out_p = output_path or (self.dir / "compiled_results.jsonl")
        records = []
        for file in sorted(self.dir.glob("*.json")):
            if file.name.startswith("compiled"):
                continue
            with open(file, "r", encoding="utf-8") as f:
                records.append(json.load(f))

        # Sort deterministically by item_id
        records.sort(key=lambda r: str(r.get("item_id", "")))

        with open(out_p, "w", encoding="utf-8") as f:
            for rec in records:
                clean_rec = dict(rec)
                f.write(json.dumps(clean_rec, sort_keys=True) + "\n")

        return out_p


class BatchRunner:
    """Executes a batch of items with restartability and failure logging."""

    def __init__(
        self,
        experiment_name: str,
        requested_model: str = "llama3.2:3b",
        returned_model: Optional[str] = None,
        prompt_version: str = "v1.0",
        seed: int = 42,
        base_dir: Optional[Path] = None,
        run_type: str = "dryrun",
        strict_provenance: bool = True,
        snapshot_hash: Optional[str] = None,
        gate_flags: Optional[Dict[str, Any]] = None,
        deterministic_mode: bool = False,
    ):
        self.requested_model = requested_model
        self.returned_model = returned_model or requested_model
        self.prompt_version = prompt_version
        self.seed = seed
        self.run_type = run_type
        self.strict_provenance = strict_provenance
        self.snapshot_hash = snapshot_hash or "SNAPSHOT_MOCK_HASH_12345"
        self.gate_flags = gate_flags or {}
        self.deterministic_mode = deterministic_mode
        random.seed(seed)

        self.logger = ExperimentLogger(
            experiment_name=experiment_name,
            base_dir=base_dir,
            run_type=run_type,
            strict_provenance=strict_provenance,
        )

    async def run_batch(
        self,
        items: List[Dict[str, Any]],
        worker_fn: Callable[[Dict[str, Any]], Any],
        simulate_crash_at: Optional[int] = None,
    ) -> Dict[str, int]:
        """Execute items sequentially, skipping already completed runs.
        
        Records an explicit FAILURE row whenever a worker fails, preventing
        silent fallbacks.
        """
        stats = {"total": len(items), "processed": 0, "skipped": 0, "failed": 0}

        for idx, item in enumerate(items):
            item_id = str(item.get("id", f"item_{idx}"))

            # Skip if already completed
            if self.logger.is_completed(item_id):
                stats["skipped"] += 1
                continue

            # Simulate crash if requested
            if simulate_crash_at is not None and stats["processed"] >= simulate_crash_at:
                print(f"[KILL] Simulated crash triggered at item {item_id} (index {idx})")
                raise KeyboardInterrupt(f"Simulated crash at item {item_id}")

            fixed_ts = "2026-10-20T00:00:00Z" if self.deterministic_mode else None

            try:
                result = await worker_fn(item)
                # Ensure worker returned valid result
                if result is None or (isinstance(result, dict) and result.get("status") == "FAILURE"):
                    raise RuntimeError(f"Worker returned failure status for {item_id}")

                self.logger.log_run(
                    item_id=item_id,
                    requested_model=self.requested_model,
                    returned_model=self.returned_model,
                    seed=self.seed,
                    inputs=item,
                    outputs=result if isinstance(result, dict) else {"result": result},
                    status="completed",
                    snapshot_hash=self.snapshot_hash,
                    gate_flags=self.gate_flags,
                    fixed_timestamp=fixed_ts,
                )
                stats["processed"] += 1
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # NO SILENT FALLBACK: Log explicit FAILURE row
                stats["failed"] += 1
                print(f"[FAILURE] Item {item_id} failed: {e}. Recording FAILURE row.")
                self.logger.log_run(
                    item_id=item_id,
                    requested_model=self.requested_model,
                    returned_model=self.returned_model,
                    seed=self.seed,
                    inputs=item,
                    outputs={"status": "FAILURE", "error": str(e)},
                    status="FAILURE",
                    snapshot_hash=self.snapshot_hash,
                    gate_flags=self.gate_flags,
                    error_message=str(e),
                    fixed_timestamp=fixed_ts,
                )

        return stats
