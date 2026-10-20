"""
app.core.provenance
--------------------
Provenance logging, manifest verification, and execution integrity tooling (R9-3).

Every experiment or pipeline run must capture:
- git commit hash
- config hash (app/ranking/config.json SHA-256)
- snapshot hash (job snapshot SHA-256)
- seed (universe / random seed)
- model name + version requested
- model name + version returned
- gate flags (e.g. seniority_gate, strict_manifest)
- run_type ('dryrun' or 'real')
- timestamp (ISO-8601 UTC)

In strict mode, a mismatch between requested model and returned model (e.g., Gemini
alias resolution gemini-3.5-flash vs gemini-3.6-flash) fails the run immediately.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

FROZEN_CONFIG_PATH = Path("app/ranking/config.json")


class ModelAliasMismatchError(RuntimeError):
    """Raised when requested model name/version does not match returned model in strict mode."""
    pass


class ProvenanceValidationError(ValueError):
    """Raised when required provenance fields are missing or invalid."""
    pass


REQUIRED_PROVENANCE_FIELDS = [
    "git_commit_hash",
    "config_hash",
    "snapshot_hash",
    "seed",
    "requested_model",
    "returned_model",
    "gate_flags",
    "run_type",
    "timestamp",
    "taxonomy_version",
    "taxonomy_hash",
]


class ProvenanceRecord(BaseModel):
    git_commit_hash: str
    config_hash: str
    snapshot_hash: str
    seed: int
    requested_model: str
    returned_model: str
    model_alias_mismatch: bool = False
    gate_flags: Dict[str, Any] = Field(default_factory=dict)
    run_type: str = Field(pattern=r"^(dryrun|real)$")
    timestamp: str
    taxonomy_version: str = "v2.1"
    taxonomy_hash: Optional[str] = None

    @field_validator(
        "git_commit_hash",
        "config_hash",
        "snapshot_hash",
        "requested_model",
        "returned_model",
        "timestamp",
        "taxonomy_version",
        "taxonomy_hash",
    )
    @classmethod
    def cannot_be_empty(cls, v: str, info) -> str:
        if not v or not str(v).strip():
            raise ProvenanceValidationError(f"Field '{info.field_name}' cannot be empty")
        return str(v).strip()


def get_git_commit_hash() -> str:
    """Retrieve the current HEAD git commit hash deterministically."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("ascii").strip()
        if out:
            return out
    except Exception:
        pass

    # Direct fallback: read .git/HEAD
    head_file = Path(".git/HEAD")
    if head_file.exists():
        ref = head_file.read_text("utf-8").strip()
        if ref.startswith("ref: "):
            ref_path = Path(".git") / ref[5:]
            if ref_path.exists():
                return ref_path.read_text("utf-8").strip()
        elif len(ref) == 40:
            return ref

    return "unknown_commit"


def get_file_sha256(path: Path | str) -> str:
    """Compute SHA-256 hash of a file."""
    p = Path(path)
    if not p.exists():
        return f"file_not_found_{p.name}"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def build_provenance_record(
    requested_model: str,
    returned_model: str,
    seed: int,
    run_type: str = "dryrun",
    snapshot_path: Optional[Path | str] = None,
    snapshot_hash: Optional[str] = None,
    config_path: Optional[Path | str] = None,
    gate_flags: Optional[Dict[str, Any]] = None,
    strict_model_match: bool = True,
) -> Dict[str, Any]:
    """Construct, validate, and return a standardized provenance record.

    Fails with ModelAliasMismatchError if strict_model_match is True and
    requested_model != returned_model.
    """
    if run_type not in ("dryrun", "real"):
        raise ProvenanceValidationError(f"Invalid run_type: '{run_type}'. Must be 'dryrun' or 'real'.")

    cfg_p = Path(config_path) if config_path else FROZEN_CONFIG_PATH
    cfg_hash = get_file_sha256(cfg_p)

    if snapshot_hash:
        snap_h = snapshot_hash
    elif snapshot_path:
        snap_h = get_file_sha256(snapshot_path)
    else:
        snap_h = "unspecified_snapshot"

    git_hash = get_git_commit_hash()
    ts = datetime.now(timezone.utc).isoformat()

    from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256
    tax_hash = get_taxonomy_sha256()
    flags = {
        "seniority_gate": getattr(settings, "SENIORITY_GATE", True),
    }
    if gate_flags:
        flags.update(gate_flags)

    # Normalize models for comparison (strip models/ or provider prefixes for comparison)
    req_norm = requested_model.lower().removeprefix("models/").strip()
    ret_norm = returned_model.lower().removeprefix("models/").strip()
    is_mismatch = (req_norm != ret_norm)

    if strict_model_match and is_mismatch:
        raise ModelAliasMismatchError(
            f"Model alias mismatch in strict mode: requested '{requested_model}' but returned '{returned_model}'."
        )

    record_data = {
        "git_commit_hash": git_hash,
        "config_hash": cfg_hash,
        "snapshot_hash": snap_h,
        "seed": seed,
        "requested_model": requested_model,
        "returned_model": returned_model,
        "model_alias_mismatch": is_mismatch,
        "gate_flags": flags,
        "run_type": run_type,
        "timestamp": ts,
        "taxonomy_version": "v2.1",
        "taxonomy_hash": tax_hash,
    }

    # Validate with Pydantic
    validated = ProvenanceRecord(**record_data)
    return validated.model_dump()


def validate_provenance_payload(payload: Dict[str, Any], strict_model_match: bool = True) -> bool:
    """Validate that an existing payload contains all required provenance fields."""
    if not isinstance(payload, dict):
        raise ProvenanceValidationError("Provenance payload must be a dict.")

    for field in REQUIRED_PROVENANCE_FIELDS:
        if field not in payload:
            raise ProvenanceValidationError(f"Missing required provenance field: '{field}'")
        val = payload[field]
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ProvenanceValidationError(f"Required provenance field '{field}' cannot be empty.")

    req = str(payload.get("requested_model", "")).lower().removeprefix("models/").strip()
    ret = str(payload.get("returned_model", "")).lower().removeprefix("models/").strip()
    if strict_model_match and req != ret:
        raise ModelAliasMismatchError(
            f"Strict validation failed: requested_model '{payload.get('requested_model')}' != returned_model '{payload.get('returned_model')}'"
        )

    # Validate using Pydantic model
    ProvenanceRecord(**payload)
    return True
