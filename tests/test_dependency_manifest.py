"""Tests verifying dependency manifest completeness and package import integrity."""

import ast
import os
import re
import sys
from pathlib import Path
import pytest


def test_core_nlp_and_pdf_libraries_import():
    """Verify that PyMuPDF (fitz), spaCy, and en_core_web_sm model are importable."""
    import fitz
    assert fitz.__doc__ is not None or hasattr(fitz, "open")

    import spacy
    assert hasattr(spacy, "load")
    nlp = spacy.load("en_core_web_sm")
    assert nlp is not None
    doc = nlp("Software Engineer with Python and FastAPI experience")
    assert len(doc) > 0


def test_redis_not_in_requirements():
    """Verify that redis is not listed in requirements.txt (as no Redis client is used in the codebase)."""
    req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    lines = req_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        cleaned = line.split("#")[0].strip()
        if cleaned:
            pkg = re.split(r"[=<>~]", cleaned)[0].strip().lower()
            assert pkg != "redis", "redis should not be in requirements.txt as no Redis client is imported"


def test_all_codebase_imports_mapped_in_requirements():
    """
    Parse AST of all Python files under app/ and scripts/ and verify that every non-stdlib,
    non-local import maps to an entry in requirements.txt.
    """
    repo_root = Path(__file__).resolve().parent.parent
    req_path = repo_root / "requirements.txt"
    assert req_path.exists(), "requirements.txt must exist"

    # Read declared packages in requirements.txt
    declared_packages = set()
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            pkg_name = re.split(r"[=<>~\[]", line)[0].strip().lower().replace("_", "-")
            declared_packages.add(pkg_name)

    # Standard library modules
    stdlib_modules = sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else {
        "os", "sys", "json", "re", "math", "time", "datetime", "uuid", "typing", "collections",
        "itertools", "functools", "pathlib", "asyncio", "logging", "hashlib", "copy", "shutil",
        "tempfile", "traceback", "inspect", "enum", "dataclasses", "unittest", "csv", "io",
        "random", "warnings", "contextlib", "subprocess", "socket", "urllib", "sqlite3", "base64",
        "secrets", "ast", "glob", "stat", "argparse", "platform", "signal", "threading", "queue",
    }

    # Project internal namespaces
    local_modules = {"app", "scripts", "tests"}

    # Mapping from Python import module name to PyPI package name in requirements.txt
    import_to_pypi = {
        "fitz": "pymupdf",
        "docx": "python-docx",
        "jwt": "pyjwt",
        "jobspy": "python-jobspy",
        "bs4": "beautifulsoup4",
        "sklearn": "scikit-learn",
        "rank_bm25": "rank-bm25",
        "sentence_transformers": "sentence-transformers",
        "json_repair": "json-repair",
        "nest_asyncio": "nest-asyncio",
        "pydantic_settings": "pydantic-settings",
        "dotenv": "python-dotenv",
        "multipart": "python-multipart",
        "pgvector": "pgvector",
        "neo4j": "neo4j",
        "chromadb": "chromadb",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "bcrypt": "bcrypt",
        "pydantic": "pydantic",
        "sqlalchemy": "sqlalchemy",
        "asyncpg": "asyncpg",
        "psycopg2": "psycopg2-binary",
        "alembic": "alembic",
        "httpx": "httpx",
        "pypdf": "pypdf",
        "pandas": "pandas",
        "tqdm": "tqdm",
        "xgboost": "xgboost",
        "shap": "shap",
        "apscheduler": "apscheduler",
        "numpy": "numpy",
        "scipy": "scipy",
        "spacy": "spacy",
        "langgraph": "langgraph",
    }

    scanned_dirs = [repo_root / "app", repo_root / "scripts"]
    unmapped_imports = set()

    for target_dir in scanned_dirs:
        for py_file in target_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            for node in ast.walk(tree):
                module_name = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.level == 0:
                        module_name = node.module.split(".")[0]

                if module_name and module_name not in stdlib_modules and module_name not in local_modules:
                    expected_pkg = import_to_pypi.get(module_name, module_name.replace("_", "-").lower())
                    if expected_pkg not in declared_packages:
                        unmapped_imports.add((module_name, str(py_file.relative_to(repo_root)), expected_pkg))

    assert not unmapped_imports, f"Found unmapped third-party imports not in requirements.txt: {unmapped_imports}"
