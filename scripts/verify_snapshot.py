"""scripts/verify_snapshot.py
-------------------------
Verifies cryptographic SHA-256 integrity of a frozen job snapshot against results/snapshots/manifest.jsonl.

Usage:
    python scripts/verify_snapshot.py <label> [--manifest results/snapshots/manifest.jsonl]
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

MANIFEST_DEFAULT = Path("results/snapshots/manifest.jsonl")
SNAPSHOT_DIR_DEFAULT = Path("data/snapshots")


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def verify_snapshot(label: str, manifest_path: Path = MANIFEST_DEFAULT, snapshots_dir: Path = SNAPSHOT_DIR_DEFAULT) -> bool:
    if not manifest_path.exists():
        print(f"Error: Manifest file not found at {manifest_path}")
        return False

    manifest_entry = None
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("label") == label:
                    manifest_entry = entry
                    break
            except Exception:
                continue

    if not manifest_entry:
        print(f"Error: Label '{label}' not found in manifest {manifest_path}")
        return False

    expected_hash = manifest_entry.get("snapshot_sha256", "").upper()
    if not expected_hash:
        print(f"Error: No snapshot_sha256 recorded for label '{label}'")
        return False

    # Find matching file in snapshots_dir
    matching_files = list(snapshots_dir.glob(f"jobs_{label}_*_adzuna.jsonl"))
    if not matching_files:
        print(f"Error: No snapshot file matching 'jobs_{label}_*_adzuna.jsonl' found in {snapshots_dir}")
        return False

    snapshot_file = matching_files[0]
    actual_hash = compute_file_sha256(snapshot_file)

    print(f"Snapshot File:  {snapshot_file}")
    print(f"Expected Hash:  {expected_hash}")
    print(f"Actual Hash:    {actual_hash}")

    if actual_hash == expected_hash:
        print(f"\n[SUCCESS] Snapshot integrity VERIFIED for '{label}'. Cryptographic hash matches manifest.")
        return True
    else:
        print(f"\n[FAILURE] Hash MISMATCH for '{label}'! File has been tampered with or corrupted.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify frozen job snapshot hash against manifest")
    parser.add_argument("label", type=str, help="Semantic snapshot label (e.g. snapshot_1)")
    parser.add_argument("--manifest", type=str, default=str(MANIFEST_DEFAULT), help="Path to manifest.jsonl")

    args = parser.parse_args()
    success = verify_snapshot(label=args.label, manifest_path=Path(args.manifest))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
