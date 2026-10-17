"""
app/ranking/performance.py
--------------------------
Inference Performance, Latency, Memory, and Cost Measurement Module (Phase 7).

Provides:
- End-to-end and per-stage latency profiling.
- Percentile latency calculations (mean, median, p90, p95, p99, min, max, std).
- Process peak memory tracking.
- Token usage aggregation and cost estimation using a configurable pricing model.
- Audit trail preserving raw repetition measurements without leaking secrets or PII.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import os
import time
import tracemalloc
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from app.core.logging import logger


# Configurable Pricing Table (USD per 1,000,000 tokens)
# Source: Public model documentation as of Phase 7 (October 2026)
DEFAULT_PRICING_TABLE: Dict[str, Dict[str, float]] = {
    # Local models: 0.00 cost
    "ollama": {"input_per_m": 0.0, "output_per_m": 0.0},
    "llama3.2:3b": {"input_per_m": 0.0, "output_per_m": 0.0},
    "llama3.1:8b": {"input_per_m": 0.0, "output_per_m": 0.0},
    # Google Gemini models
    "gemini-2.0-flash": {"input_per_m": 0.10, "output_per_m": 0.40},
    "gemini-1.5-flash": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-1.5-pro": {"input_per_m": 1.25, "output_per_m": 5.00},
    # OpenAI models
    "gpt-4o-mini": {"input_per_m": 0.15, "output_per_m": 0.60},
    "gpt-4o": {"input_per_m": 2.50, "output_per_m": 10.00},
    # Anthropic models
    "claude-3-5-sonnet": {"input_per_m": 3.00, "output_per_m": 15.00},
    "claude-3-5-haiku": {"input_per_m": 0.80, "output_per_m": 4.00},
}


def calculate_token_cost(
    model_name: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    pricing_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> Optional[float]:
    """
    Calculate estimated cost in USD based on input and output token counts.
    Returns None if token counts are unavailable or model is unpriced (except local Ollama).
    """
    if prompt_tokens is None and completion_tokens is None:
        return None

    p_tokens = prompt_tokens or 0
    c_tokens = completion_tokens or 0

    table = pricing_table or DEFAULT_PRICING_TABLE
    norm_name = model_name.lower().removeprefix("models/")

    # Find matching rate
    rate = None
    for k, v in table.items():
        if k in norm_name or norm_name in k:
            rate = v
            break

    if rate is None:
        # If it's explicitly an ollama/local run
        if "ollama" in norm_name or "llama" in norm_name:
            return 0.0
        return None

    cost_in = (p_tokens / 1_000_000.0) * rate.get("input_per_m", 0.0)
    cost_out = (c_tokens / 1_000_000.0) * rate.get("output_per_m", 0.0)
    return round(cost_in + cost_out, 6)


@dataclass
class StageTimer:
    """Tracks latency for discrete stages within a pipeline invocation."""
    stage_durations_ms: Dict[str, float] = field(default_factory=dict)
    _active_starts: Dict[str, float] = field(default_factory=dict)

    @contextmanager
    def time_stage(self, stage_name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.stage_durations_ms[stage_name] = round(elapsed_ms, 3)


@dataclass
class SingleRunMeasurement:
    """Metrics for an individual execution repetition."""
    repetition_index: int
    success: bool
    total_latency_ms: float
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    peak_memory_mb: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class PerformanceBenchmarkTracker:
    """Manages performance benchmarking across multiple repetitions."""

    def __init__(
        self,
        provider: str = "local",
        model: str = "hybrid_ranker",
        prompt_version: str = "v1.0",
        pricing_table: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.pricing_table = pricing_table or DEFAULT_PRICING_TABLE
        self.raw_measurements: List[SingleRunMeasurement] = []

    def record_run(
        self,
        total_latency_ms: float,
        success: bool = True,
        stage_latencies_ms: Optional[Dict[str, float]] = None,
        peak_memory_mb: Optional[float] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> SingleRunMeasurement:
        """Record an individual measurement into the audit history."""
        total_tokens = None
        if prompt_tokens is not None or completion_tokens is not None:
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

        cost = calculate_token_cost(
            model_name=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            pricing_table=self.pricing_table,
        )

        measurement = SingleRunMeasurement(
            repetition_index=len(self.raw_measurements) + 1,
            success=success,
            total_latency_ms=round(total_latency_ms, 3),
            stage_latencies_ms=stage_latencies_ms or {},
            peak_memory_mb=round(peak_memory_mb, 2) if peak_memory_mb is not None else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            error_type=error_type,
            error_message=str(error_message)[:200] if error_message else None,
        )
        self.raw_measurements.append(measurement)
        return measurement

    def compute_summary(self) -> Dict[str, Any]:
        """Aggregate all collected measurements into percentiles and summary statistics."""
        if not self.raw_measurements:
            return {
                "provider": self.provider,
                "model": self.model,
                "prompt_version": self.prompt_version,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "error_rate": 0.0,
                "latency_summary_ms": {},
                "cost_summary": {},
            }

        total_runs = len(self.raw_measurements)
        successful_runs = [m for m in self.raw_measurements if m.success]
        failed_runs = [m for m in self.raw_measurements if not m.success]
        error_rate = len(failed_runs) / total_runs

        # Latency statistics on successful runs
        latencies = [m.total_latency_ms for m in successful_runs]
        if latencies:
            lat_summary = {
                "count": len(latencies),
                "mean_ms": round(float(np.mean(latencies)), 2),
                "median_ms": round(float(np.median(latencies)), 2),
                "std_ms": round(float(np.std(latencies)), 2),
                "min_ms": round(float(min(latencies)), 2),
                "max_ms": round(float(max(latencies)), 2),
                "p90_ms": round(float(np.percentile(latencies, 90)), 2),
                "p95_ms": round(float(np.percentile(latencies, 95)), 2),
                "p99_ms": round(float(np.percentile(latencies, 99)), 2),
            }
        else:
            lat_summary = {"count": 0, "note": "No successful runs to compute latency statistics."}

        # Per-stage latency aggregation
        stage_names: set = set()
        for m in successful_runs:
            stage_names.update(m.stage_latencies_ms.keys())

        stage_breakdown: Dict[str, Dict[str, float]] = {}
        for st in sorted(stage_names):
            vals = [m.stage_latencies_ms[st] for m in successful_runs if st in m.stage_latencies_ms]
            if vals:
                stage_breakdown[st] = {
                    "mean_ms": round(float(np.mean(vals)), 2),
                    "median_ms": round(float(np.median(vals)), 2),
                    "p95_ms": round(float(np.percentile(vals, 95)), 2),
                }

        # Memory usage
        mem_vals = [m.peak_memory_mb for m in self.raw_measurements if m.peak_memory_mb is not None]
        mem_summary = {
            "peak_mb": round(max(mem_vals), 2) if mem_vals else None,
            "mean_mb": round(float(np.mean(mem_vals)), 2) if mem_vals else None,
        }

        # Token & cost statistics
        total_prompt_tokens = sum(m.prompt_tokens or 0 for m in successful_runs if m.prompt_tokens is not None)
        total_comp_tokens = sum(m.completion_tokens or 0 for m in successful_runs if m.completion_tokens is not None)
        has_token_data = any(m.prompt_tokens is not None for m in successful_runs)

        costs = [m.estimated_cost_usd for m in successful_runs if m.estimated_cost_usd is not None]
        total_cost = round(sum(costs), 6) if costs else (0.0 if "ollama" in self.provider.lower() else None)

        cost_summary = {
            "token_tracking_available": has_token_data,
            "total_prompt_tokens": total_prompt_tokens if has_token_data else None,
            "total_completion_tokens": total_comp_tokens if has_token_data else None,
            "total_tokens": (total_prompt_tokens + total_comp_tokens) if has_token_data else None,
            "total_cost_usd": total_cost,
            "mean_cost_per_run_usd": round(float(np.mean(costs)), 6) if costs else (0.0 if "ollama" in self.provider.lower() else None),
        }

        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "total_runs": total_runs,
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "error_rate": round(error_rate, 4),
            "latency_summary_ms": lat_summary,
            "stage_latencies": stage_breakdown,
            "memory_summary": mem_summary,
            "cost_summary": cost_summary,
            "raw_measurements_count": len(self.raw_measurements),
        }


@contextmanager
def measure_execution_memory():
    """Context manager measuring peak memory allocated during execution using tracemalloc."""
    tracemalloc.start()
    try:
        yield
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()


def benchmark_function_sync(
    fn: Callable[[], Any],
    n_repetitions: int = 5,
    provider: str = "local",
    model: str = "function",
    prompt_version: str = "v1.0",
) -> Dict[str, Any]:
    """Run synchronous function benchmark across n_repetitions."""
    tracker = PerformanceBenchmarkTracker(provider=provider, model=model, prompt_version=prompt_version)

    for i in range(n_repetitions):
        tracemalloc.start()
        t0 = time.perf_counter()
        success = True
        err_type = None
        err_msg = None

        try:
            fn()
        except Exception as exc:
            success = False
            err_type = type(exc).__name__
            err_msg = str(exc)
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_mb = peak / (1024.0 * 1024.0)

            tracker.record_run(
                total_latency_ms=elapsed_ms,
                success=success,
                peak_memory_mb=peak_mb,
                error_type=err_type,
                error_message=err_msg,
            )

    return tracker.compute_summary()
