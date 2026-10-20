"""
scripts.create_checkpoint
-------------------------
Checkpoint Tooling (R9-7):
Freezes documents, computes cryptographic hashes, writes an immutable manifest,
and creates a local git tag. Refuses to proceed if the working tree is dirty.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_ASSET_PATHS = [
    "app/ranking/config.json",
    "data/evaluation/query_intent_benchmark_v1.json",
    "data/evaluation/rag_coach_eval_v1.json",
    "data/router/test.jsonl",
    "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
    "artifacts/models/intent_router_v1.joblib",
    "artifacts/models/matcher_xgboost.json",
]


def check_git_clean(repo_dir: Path | str = ".") -> Tuple[bool, str]:
    """Check if the git working tree is clean. Returns (is_clean, status_output)."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        status_text = proc.stdout.strip()
        return (len(status_text) == 0, status_text)
    except Exception as e:
        raise RuntimeError(f"Failed to check git status in {repo_dir}: {e}")


def compute_file_sha256(path: Path | str) -> str:
    """Compute uppercase SHA-256 hash of a file."""
    p = Path(path)
    if not p.exists():
        return f"MISSING_{p.name}"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def get_git_commit(repo_dir: Path | str = ".") -> str:
    """Get current HEAD commit hash."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def create_git_tag(tag_name: str, message: str, repo_dir: Path | str = ".") -> None:
    """Create a local annotated git tag."""
    subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", message],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
    )


def create_checkpoint(
    tag_name: str,
    asset_paths: Optional[List[str]] = None,
    repo_dir: Path | str = ".",
    manifests_dir: Optional[Path | str] = None,
    allow_dirty: bool = False,
) -> Dict[str, Any]:
    """Execute checkpointing: verify clean tree, compute hashes, write manifest, create git tag."""
    repo_path = Path(repo_dir).resolve()

    # 1. Refuse if tree is dirty
    is_clean, status_text = check_git_clean(repo_path)
    if not is_clean and not allow_dirty:
        raise RuntimeError(
            f"Checkpoint refused: working tree in '{repo_path}' is dirty.\n"
            f"Uncommitted changes:\n{status_text}\n"
            f"Commit or stash all changes before creating a formal checkpoint."
        )

    # 2. Compute hashes of key assets
    paths = asset_paths or DEFAULT_ASSET_PATHS
    asset_hashes: Dict[str, str] = {}
    for rel_p in paths:
        full_p = repo_path / rel_p
        asset_hashes[rel_p] = compute_file_sha256(full_p)

    commit_hash = get_git_commit(repo_path)

    # 3. Build manifest
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    manifest = {
        "tag": tag_name,
        "commit_hash": commit_hash,
        "timestamp": ts,
        "assets_sha256": asset_hashes,
        "status": "clean" if is_clean else "dirty_override",
    }

    # Write manifest file
    out_dir = Path(manifests_dir) if manifests_dir else (repo_path / "artifacts" / "checkpoints")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = out_dir / f"{tag_name}_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    # 4. Create annotated git tag
    tag_msg = f"Checkpoint {tag_name} created at {ts} [commit: {commit_hash[:8]}]"
    create_git_tag(tag_name, tag_msg, repo_dir=repo_path)

    return {
        "manifest_file": str(manifest_file),
        "tag": tag_name,
        "commit": commit_hash,
        "manifest": manifest,
    }


def main():
    parser = argparse.ArgumentParser(description="Create immutable checkpoint: hash assets, write manifest, tag git.")
    parser.add_argument("--tag", type=str, required=True, help="Tag name (e.g. checkpoint-a, checkpoint-b)")
    parser.add_argument("--allow-dirty", action="store_true", default=False, help="Allow dirty tree override (for testing only)")
    parser.add_argument("--manifests-dir", type=str, default=None, help="Directory to store manifest JSON")
    args = parser.parse_args()

    try:
        res = create_checkpoint(
            tag_name=args.tag,
            allow_dirty=args.allow_dirty,
            manifests_dir=args.manifests_dir,
        )
        print("================ CHECKPOINT CREATION SUCCESS ================")
        print(f"  Tag:      {res['tag']}")
        print(f"  Commit:   {res['commit']}")
        print(f"  Manifest: {res['manifest_file']}")
        print("Asset Hashes:")
        for k, v in res["manifest"]["assets_sha256"].items():
            print(f"    {k:50s} : {v}")
    except RuntimeError as err:
        print("================ CHECKPOINT REFUSED ================", file=sys.stderr)
        print(str(err), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
