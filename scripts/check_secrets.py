#!/usr/bin/env python3
"""
scripts/check_secrets.py
------------------------
Repository secret scanner for Phase B/C (Prompt P0).

Scans repository files for sensitive credentials, including:
1. Google AI API key patterns (AIza...)
2. Google Gemini / OAuth token patterns (AQ.Ab...)
3. Groq API key patterns (gsk_...)
4. Exact values of sensitive API keys defined in the local .env file.

Security Safeguards:
- NEVER prints or displays complete secret values or credentials.
- Reports only file paths, line numbers, and pattern/variable identifiers.
- Exits with non-zero code (1) if any secret pattern or credential is detected.

Usage:
  # Scan Git staged index files (recommended for pre-commit hooks):
  python scripts/check_secrets.py --staged

  # Scan entire repository (excluding virtual environments and git metadata):
  python scripts/check_secrets.py

  # Scan specific target directories:
  python scripts/check_secrets.py artifacts docs
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Pattern, Set, Tuple, Union

# Built-in regex patterns for credentials
SECRET_PATTERNS: List[Tuple[str, Pattern]] = [
    ("Google API Key (AIza...)", re.compile(r"\bAIza[0-9A-Za-z-_]{30,40}\b")),
    ("Gemini / Google Token (AQ.Ab...)", re.compile(r"\bAQ\.Ab[0-9A-Za-z-_]+\b")),
    ("Groq API Key (gsk_...)", re.compile(r"\bgsk_[0-9A-Za-z]{30,}\b")),
]

# Standard placeholder values to ignore
IGNORED_ENV_VALUES: Set[str] = {
    "",
    "your_secret_key_here",
    "your_gemini_api_key_here",
    "your_openai_api_key_here",
    "your_anthropic_api_key_here",
    "temporary-dev-secret-key-change-in-production",
    "dev-secret-key-change-in-production-ai-career-copilot-2025",
    "change-me-to-a-secure-random-secret-key-min-32-chars",
    "postgres",
    "career_neo4j_2025",
    "development",
    "production",
    "localhost",
    "ai_career_copilot",
}

DEFAULT_EXCLUDED_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".pytest_cache",
    "__pycache__",
    ".tox",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

DEFAULT_EXCLUDED_FILES: Set[str] = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
}


def should_exclude_dir(dir_name: str, excluded_dirs: Optional[Set[str]] = None) -> bool:
    """Check if directory name matches excluded set or virtual-environment prefixes/patterns."""
    dirs_to_check = excluded_dirs if excluded_dirs is not None else DEFAULT_EXCLUDED_DIRS
    if dir_name in dirs_to_check:
        return True
    # Prune .venv, .venv-*, venv, venv-*, env, env-*
    if dir_name.startswith((".venv", "venv", ".env_")):
        return True
    if dir_name == "env" or dir_name.startswith("env-"):
        return True
    return False


def should_exclude_path(
    rel_path: Union[str, Path],
    excluded_dirs: Optional[Set[str]] = None,
    excluded_files: Optional[Set[str]] = None,
) -> bool:
    """Check if a file path belongs to an excluded directory or is an excluded/env file."""
    path_obj = Path(rel_path)
    # Check parent directory components
    for part in path_obj.parts[:-1]:
        if should_exclude_dir(part, excluded_dirs):
            return True

    # Check file name
    files_to_check = excluded_files if excluded_files is not None else DEFAULT_EXCLUDED_FILES
    fname = path_obj.name
    if fname in files_to_check:
        return True
    # Skip .env and environment files, but allow .env.example
    if fname == ".env" or (fname.startswith(".env.") and not fname.endswith(".example")):
        return True
    return False


def is_binary_content(raw_bytes: bytes) -> bool:
    """Check if raw byte content appears to be binary."""
    return b"\x00" in raw_bytes[:8192]


def load_env_secrets(env_path: Path) -> Dict[str, str]:
    """Extract sensitive credential values from .env without exposing them."""
    secrets: Dict[str, str] = {}
    if not env_path.is_file():
        return secrets

    try:
        content = env_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return secrets

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")

            # Only track actual secret fields (API keys, tokens, secret passwords)
            is_secret_name = any(t in key.upper() for t in ("KEY", "SECRET", "TOKEN", "AUTH"))
            if is_secret_name and len(val) >= 12 and val not in IGNORED_ENV_VALUES:
                secrets[key] = val

    return secrets


def scan_content(
    content: str,
    patterns: List[Tuple[str, Pattern]],
    env_secrets: Dict[str, str],
) -> List[Tuple[int, str]]:
    """Scan string content line by line for secret patterns and env values. Returns (line_no, match_desc)."""
    findings: List[Tuple[int, str]] = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        matched = False
        for pat_name, pat in patterns:
            if pat.search(line):
                findings.append((idx, f"Pattern: {pat_name}"))
                matched = True
                break

        if not matched:
            for env_key, secret_val in env_secrets.items():
                if secret_val in line:
                    findings.append((idx, f"Matches .env variable: {env_key}"))
                    break

    return findings


def scan_file(
    file_path: Path,
    patterns: List[Tuple[str, Pattern]],
    env_secrets: Dict[str, str],
) -> List[Tuple[int, str]]:
    """Scan a single file for secret patterns and env values. Returns (line_no, match_desc)."""
    try:
        raw = file_path.read_bytes()
    except Exception:
        return []

    if is_binary_content(raw):
        return []

    try:
        content = raw.decode("utf-8-sig", errors="ignore")
    except Exception:
        return []

    return scan_content(content, patterns, env_secrets)


def scan_repository(
    target_paths: List[Path],
    repo_root: Path,
    env_secrets: Dict[str, str],
    excluded_dirs: Set[str] = DEFAULT_EXCLUDED_DIRS,
    excluded_files: Set[str] = DEFAULT_EXCLUDED_FILES,
) -> List[Tuple[Path, int, str]]:
    """Recursively scan files in target_paths for secrets with directory pruning."""
    all_findings: List[Tuple[Path, int, str]] = []

    for target in target_paths:
        if not target.exists():
            continue

        if target.is_file():
            try:
                rel = target.relative_to(repo_root)
            except ValueError:
                rel = target
            if should_exclude_path(rel, excluded_dirs, excluded_files):
                continue
            findings = scan_file(target, SECRET_PATTERNS, env_secrets)
            for line_no, desc in findings:
                all_findings.append((target, line_no, desc))
            continue

        for root, dirs, files in os.walk(target, followlinks=False):
            # Prune excluded directories in-place so os.walk does not recurse into them
            dirs[:] = [d for d in dirs if not should_exclude_dir(d, excluded_dirs)]

            for fname in files:
                file_path = Path(root) / fname
                try:
                    rel = file_path.relative_to(repo_root)
                except ValueError:
                    rel = file_path

                if should_exclude_path(rel, excluded_dirs, excluded_files):
                    continue

                findings = scan_file(file_path, SECRET_PATTERNS, env_secrets)
                for line_no, desc in findings:
                    all_findings.append((file_path, line_no, desc))

    return all_findings


def get_staged_files(repo_root: Path) -> List[str]:
    """Return a list of staged file paths (added, copied, modified, renamed destination), skipping deleted."""
    cmd = ["git", "diff", "--cached", "--name-status", "-z"]
    try:
        res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Git executable not found in PATH.") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to execute git diff: {exc}") from exc

    if res.returncode != 0:
        err_msg = res.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Git command failed (exit code {res.returncode}): {err_msg}")

    parts = res.stdout.split(b"\x00")
    staged_files: List[str] = []
    i = 0
    while i < len(parts) - 1:
        status_raw = parts[i]
        if not status_raw:
            break
        status = status_raw.decode("utf-8", errors="replace")
        if status.startswith("R") or status.startswith("C"):
            # Rename or Copy: format is <status>\0<src_path>\0<dst_path>\0
            if i + 2 < len(parts):
                dst_path = parts[i + 2].decode("utf-8", errors="replace")
                staged_files.append(dst_path)
            i += 3
        else:
            # Added, Modified, Deleted, etc.: format is <status>\0<path>\0
            if i + 1 < len(parts):
                path = parts[i + 1].decode("utf-8", errors="replace")
                if status != "D":  # Skip deleted files
                    staged_files.append(path)
            i += 2

    return staged_files


def get_staged_file_content(git_path: str, repo_root: Path) -> Optional[bytes]:
    """Retrieve raw staged index content for git_path via `git show :0:<path>`."""
    normalized_path = git_path.replace("\\", "/")
    cmd = ["git", "show", f":0:{normalized_path}"]
    try:
        res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to execute git show for '{git_path}': {exc}") from exc

    if res.returncode != 0:
        return None
    return res.stdout


def scan_staged(
    repo_root: Path,
    env_secrets: Dict[str, str],
    patterns: Optional[List[Tuple[str, Pattern]]] = None,
    excluded_dirs: Optional[Set[str]] = None,
    excluded_files: Optional[Set[str]] = None,
) -> List[Tuple[str, int, str]]:
    """Scan all staged files from Git index. Returns list of (git_path, line_no, match_desc)."""
    pats = patterns if patterns is not None else SECRET_PATTERNS
    staged_paths = get_staged_files(repo_root)
    all_findings: List[Tuple[str, int, str]] = []

    for git_path in staged_paths:
        if should_exclude_path(git_path, excluded_dirs, excluded_files):
            continue

        raw_bytes = get_staged_file_content(git_path, repo_root)
        if raw_bytes is None:
            continue

        if is_binary_content(raw_bytes):
            continue

        try:
            content = raw_bytes.decode("utf-8-sig", errors="ignore")
        except Exception:
            continue

        file_findings = scan_content(content, pats, env_secrets)
        for line_no, desc in file_findings:
            all_findings.append((git_path, line_no, desc))

    return all_findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Repository Secret Scanner")
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        help="Directories or files to scan (default: repository root).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan git staged index files instead of working tree directories.",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=".env",
        help="Path to .env file to extract credential values from.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(".").resolve()
    env_path = repo_root / args.env_file
    env_secrets = load_env_secrets(env_path)

    try:
        if args.staged:
            staged_findings = scan_staged(
                repo_root=repo_root,
                env_secrets=env_secrets,
            )
            findings: List[Tuple[Union[Path, str], int, str]] = [
                (p, line_no, desc) for p, line_no, desc in staged_findings
            ]
        else:
            scan_paths = [Path(p).resolve() for p in args.paths] if args.paths else [repo_root]
            repo_findings = scan_repository(
                target_paths=scan_paths,
                repo_root=repo_root,
                env_secrets=env_secrets,
            )
            findings = [
                (p, line_no, desc) for p, line_no, desc in repo_findings
            ]
    except Exception as exc:
        sys.stderr.write(f"[ERROR] Secret scan execution failed: {exc}\n")
        return 1

    if findings:
        scan_scope = "staged" if args.staged else "repository"
        print(f"[SECURITY ALERT] Found {len(findings)} potential secret(s) in {scan_scope} files:\n")
        for fpath, line_no, desc in findings:
            if isinstance(fpath, Path):
                try:
                    display_path = str(fpath.relative_to(repo_root)).replace("\\", "/")
                except ValueError:
                    display_path = str(fpath).replace("\\", "/")
            else:
                display_path = str(fpath).replace("\\", "/")
            print(f"  FAILED: {display_path}:{line_no} -> {desc}")
        print("\nPlease redact secrets with [REDACTED_KEY] before committing.")
        return 1

    scan_type = "staged" if args.staged else "repository"
    print(f"[SUCCESS] Secret scan passed ({scan_type}). No exposed secrets or key patterns detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
