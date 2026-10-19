"""Adzuna API Quota Guard & Persistent Call Counter (Remediation R8).

Enforces strict client-side quota controls on Adzuna API invocations:
- Tracks all outgoing HTTP calls in a persistent JSON ledger: `data/ingest/adzuna_call_counter.json`.
- Increments the counter BEFORE every request is sent (including retries).
- Refuses to dispatch any request that would exceed the configured ADZUNA_CALL_BUDGET (default 20).
- Limits retries to at most 1 attempt (for transient errors only); zero retries on 4xx.
- Halts execution immediately on HTTP 429 (Rate Limit) or HTTP 401/403 (Auth Error).
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.core.redaction import redact_credentials, redact_url

DEFAULT_COUNTER_FILE = Path("data/ingest/adzuna_call_counter.json")


class QuotaExceededError(RuntimeError):
    """Raised when an Adzuna API request would exceed the configured call budget."""
    pass


class AdzunaRateLimitError(RuntimeError):
    """Raised when Adzuna returns HTTP 429 (Too Many Requests), terminating the run."""
    pass


class AdzunaAuthError(RuntimeError):
    """Raised when Adzuna returns HTTP 401/403, indicating invalid or inactive credentials."""
    pass


class AdzunaQuotaGuard:
    """Thread-safe persistent quota controller for Adzuna API requests."""

    def __init__(
        self,
        counter_file: Path = DEFAULT_COUNTER_FILE,
        budget: Optional[int] = None,
    ):
        self.counter_file = Path(counter_file)
        self._explicit_budget = budget
        self._lock = threading.Lock()

    @property
    def budget(self) -> int:
        if self._explicit_budget is not None:
            return self._explicit_budget
        env_budget = os.environ.get("ADZUNA_CALL_BUDGET")
        if env_budget:
            try:
                return int(env_budget)
            except ValueError:
                pass
        return getattr(settings, "ADZUNA_CALL_BUDGET", 20)

    def _ensure_dir(self) -> None:
        self.counter_file.parent.mkdir(parents=True, exist_ok=True)

    def _read_data(self) -> Dict[str, Any]:
        self._ensure_dir()
        if not self.counter_file.exists():
            return {
                "total_calls": 0,
                "budget": self.budget,
                "last_call_at": None,
                "history": [],
            }
        try:
            with open(self.counter_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to read Adzuna counter file {self.counter_file}: {exc}. Initializing fresh state.")
            return {
                "total_calls": 0,
                "budget": self.budget,
                "last_call_at": None,
                "history": [],
            }

    def _write_data(self, data: Dict[str, Any]) -> None:
        self._ensure_dir()
        # Atomic write via temporary file
        temp_file = self.counter_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.counter_file)

    def get_calls_used(self) -> int:
        """Return total calls recorded in the counter file."""
        with self._lock:
            data = self._read_data()
            return int(data.get("total_calls", 0))

    def get_calls_remaining(self) -> int:
        """Return remaining calls within budget."""
        return max(0, self.budget - self.get_calls_used())

    def check_can_call(self) -> None:
        """Verify whether an outgoing API call is permitted under the budget."""
        calls_used = self.get_calls_used()
        if calls_used >= self.budget:
            msg = (
                f"Adzuna API call refused: call budget of {self.budget} reached "
                f"({calls_used} calls used, 0 remaining). Execution halted by quota guard."
            )
            logger.error(msg)
            raise QuotaExceededError(msg)

    def record_call_before_send(
        self,
        endpoint: str,
        query: Optional[str] = None,
        city: Optional[str] = None,
        page: int = 1,
        is_retry: bool = False,
    ) -> int:
        """
        Record and persist an API call BEFORE sending the HTTP request.
        Raises QuotaExceededError if the budget is reached.
        Returns the new total calls count.
        """
        with self._lock:
            data = self._read_data()
            current_calls = int(data.get("total_calls", 0))

            if current_calls >= self.budget:
                msg = (
                    f"Adzuna API call refused: call budget of {self.budget} reached "
                    f"({current_calls} calls used, 0 remaining). Cannot send request."
                )
                logger.error(msg)
                raise QuotaExceededError(msg)

            new_total = current_calls + 1
            now_iso = datetime.now(timezone.utc).isoformat()

            entry = {
                "call_index": new_total,
                "timestamp": now_iso,
                "endpoint": redact_url(endpoint),
                "query": query,
                "city": city,
                "page": page,
                "is_retry": is_retry,
                "status_code": None,
            }

            data["total_calls"] = new_total
            data["budget"] = self.budget
            data["last_call_at"] = now_iso
            history: List[Dict[str, Any]] = data.get("history", [])
            history.append(entry)
            data["history"] = history

            self._write_data(data)
            logger.info(
                f"[Adzuna Quota] Recorded call #{new_total}/{self.budget} "
                f"(query='{query}', city='{city}', page={page}, retry={is_retry})"
            )
            return new_total

    def record_call_result(
        self,
        call_index: int,
        status_code: int,
        duration_ms: float = 0.0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update result status code and latency for a recorded call."""
        with self._lock:
            data = self._read_data()
            for entry in reversed(data.get("history", [])):
                if entry.get("call_index") == call_index:
                    entry["status_code"] = status_code
                    entry["duration_ms"] = round(duration_ms, 2)
                    if error_message:
                        entry["error"] = redact_credentials(error_message)
                    break
            self._write_data(data)

    def print_quota_summary(self) -> Dict[str, Any]:
        """Log and return human-readable quota utilization summary."""
        used = self.get_calls_used()
        rem = self.get_calls_remaining()
        summary = {
            "calls_used": used,
            "calls_budget": self.budget,
            "calls_remaining": rem,
            "quota_limited": used >= self.budget,
        }
        print(f"\n================ ADZUNA QUOTA SUMMARY ================")
        print(f"Calls Used:      {used} / {self.budget}")
        print(f"Calls Remaining: {rem}")
        print(f"Status:          {'QUOTA LIMIT REACHED' if used >= self.budget else 'WITHIN BUDGET'}")
        print(f"======================================================\n")
        logger.info(f"Adzuna Quota Summary: {summary}")
        return summary

    def reset_for_testing(self, initial_calls: int = 0) -> None:
        """Reset counter file for automated testing purposes only."""
        with self._lock:
            data = {
                "total_calls": initial_calls,
                "budget": self.budget,
                "last_call_at": datetime.now(timezone.utc).isoformat() if initial_calls > 0 else None,
                "history": [],
            }
            self._write_data(data)


# Global singleton quota guard
adzuna_quota_guard = AdzunaQuotaGuard()
