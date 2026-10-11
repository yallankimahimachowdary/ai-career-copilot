"""Experiment Run Logger and Resumable Batch Runner."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time
from typing import Any, Callable, Dict, List, Optional

EXPERIMENTS_DIR = Path("artifacts/experiments/runs")
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = EXPERIMENTS_DIR / "completed_runs.json"


class ExperimentLogger:
    """Logs individual experiment executions to structured JSON files."""

    def __init__(self, experiment_name: str = "default_experiment"):
        self.experiment_name = experiment_name
        self.dir = EXPERIMENTS_DIR / experiment_name
        self.dir.mkdir(parents=True, exist_ok=True)

    def is_completed(self, item_id: str) -> bool:
        """Check if an item has already been successfully recorded."""
        record_path = self.dir / f"{item_id}.json"
        return record_path.exists()

    def log_run(
        self,
        item_id: str,
        model: str,
        prompt_version: str,
        seed: int,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        provider: str = "ollama",
        status: str = "completed",
    ) -> Path:
        """Persist experiment output with metadata and timestamp."""
        ts = datetime.now(timezone.utc).isoformat()
        payload = {
            "item_id": item_id,
            "experiment_name": self.experiment_name,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "seed": seed,
            "status": status,
            "timestamp": ts,
            "inputs": inputs,
            "outputs": outputs,
        }
        file_path = self.dir / f"{item_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        return file_path


class BatchRunner:
    """Executes a batch of items with restartability, skipping completed items."""

    def __init__(
        self,
        experiment_name: str,
        model: str = "llama3.2:3b",
        prompt_version: str = "v1.0",
        seed: int = 42,
    ):
        self.logger = ExperimentLogger(experiment_name=experiment_name)
        self.model = model
        self.prompt_version = prompt_version
        self.seed = seed
        random.seed(seed)

    async def run_batch(
        self,
        items: List[Dict[str, Any]],
        worker_fn: Callable[[Dict[str, Any]], Any],
        simulate_crash_at: Optional[int] = None,
    ) -> Dict[str, int]:
        """Execute items sequentially, skipping already completed runs."""
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

            try:
                result = await worker_fn(item)
                self.logger.log_run(
                    item_id=item_id,
                    model=self.model,
                    prompt_version=self.prompt_version,
                    seed=self.seed,
                    inputs=item,
                    outputs=result if isinstance(result, dict) else {"result": result},
                )
                stats["processed"] += 1
            except Exception as e:
                stats["failed"] += 1
                print(f"[Error] Failed processing item {item_id}: {e}")

        return stats
