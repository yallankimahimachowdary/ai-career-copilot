#!/usr/bin/env python3
"""
scripts/intake_resumes.py
-------------------------
Real-resume intake and anonymization processor (Remediation R14-1).

Features:
- Takes a folder of real PDF resumes as input.
- Validates that real and synthetic resumes are NEVER mixed:
  Refuses to proceed if synthetic filenames ("SYN_") or synthetic footers
  ("Synthetic test resume - fictional person, not real data") are detected.
- Extracts plain text using robust PyMuPDF / pypdf extraction.
- Anonymizes PII immediately: removes names, phones, emails, and academic institutions.
- Parses canonical skills using FROZEN taxonomy v2.1.
- Classifies candidate into one of the 9 role families.
- Evaluates in-scope vs out-of-scope status according to docs/eval_scope.json:
  (In-scope: Data/AI, Web/Software, Cybersecurity/Cloud).
- Gating and destination safety:
  Real processed candidates write strictly to results/real/ (never results/dryrun/).
  Dryrun mode writes strictly to results/dryrun/.
- Records detailed parsing and intake report:
  Counts per family, in-scope vs out-of-scope counts, parse failure reasons
  (e.g., scanned PDF, two-column layout, empty text), average skills per resume,
  and zero PII verification.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.provenance import get_git_commit_hash, get_file_sha256, FROZEN_CONFIG_PATH
from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256
from app.services.anonymizer import anonymize_resume
from app.services.extractor import extract_text_from_pdf, ExtractionError
from app.services.parser_agent import parser_agent
from scripts.build_universes import load_eval_scope, classify_resume_family


SYNTHETIC_FOOTER_SIGNATURE = "synthetic test resume - fictional person, not real data"


class ResumeContaminationError(ValueError):
    """Raised when real and synthetic resumes are mixed together."""
    pass


def detect_synthetic_contamination(pdf_path: Path, raw_text: str) -> bool:
    """Check whether a resume is synthetic based on filename prefix or synthetic footer."""
    if pdf_path.name.upper().startswith("SYN_"):
        return True
    if SYNTHETIC_FOOTER_SIGNATURE in raw_text.lower():
        return True
    return False


def verify_zero_pii_in_text(anonymized_text: str) -> Tuple[bool, List[str]]:
    """Verify that anonymized text contains zero unmasked PII (emails, phone numbers)."""
    leaks = []
    # Email pattern
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    # Phone pattern (standard 10-digit Indian/international formats)
    phone_pattern = re.compile(r"(?:\+91[\s-]?)?[6789]\d{9}\b")

    for match in email_pattern.finditer(anonymized_text):
        leaks.append(f"email_leak:{match.group(0)}")
    for match in phone_pattern.finditer(anonymized_text):
        leaks.append(f"phone_leak:{match.group(0)}")

    return (len(leaks) == 0, leaks)


def process_resume_intake(
    resumes_dir: Path | str,
    output_dir: Optional[Path | str] = None,
    run_type: str = "real",
    allow_synthetic: bool = False,
) -> Dict[str, Any]:
    """Process a directory of resumes, extract, anonymize, classify, and generate intake report."""
    in_dir = Path(resumes_dir)
    if not in_dir.exists():
        raise FileNotFoundError(f"Resumes directory not found: {in_dir}")

    # Destination gating (R14-1, R16-1)
    if run_type == "real":
        dest_dir = Path(output_dir) if output_dir else Path("results/real")
    elif run_type == "synthetic_eval":
        dest_dir = Path(output_dir) if output_dir else Path("results/synthetic_eval")
    else:
        dest_dir = Path(output_dir) if output_dir else Path("results/dryrun")
    dest_dir.mkdir(parents=True, exist_ok=True)

    in_scope_families, deficit_families = load_eval_scope()

    pdf_files = sorted(list(in_dir.glob("*.pdf")))
    if not pdf_files:
        raise ValueError(f"No PDF resumes found in: {in_dir}")

    processed_candidates: List[Dict[str, Any]] = []
    parse_failures: List[Dict[str, Any]] = []
    family_counts: Dict[str, int] = {}
    in_scope_count = 0
    out_of_scope_count = 0
    total_skills_extracted = 0

    # Contamination check: count synthetic vs real
    synthetic_detected: Set[str] = set()

    for pdf_path in pdf_files:
        cand_id = pdf_path.stem
        # Check filename contamination immediately
        if pdf_path.name.startswith("SYN_"):
            synthetic_detected.add(pdf_path.name)
        raw_bytes = pdf_path.read_bytes()

        # Step 1: Text extraction
        raw_text = ""
        extraction_engine = "none"
        try:
            raw_text, extraction_engine = extract_text_from_pdf(raw_bytes, return_engine=True)
            raw_text = raw_text.strip()
        except ExtractionError as e:
            parse_failures.append({
                "candidate_id": cand_id,
                "file_name": pdf_path.name,
                "reason": "empty_text_or_extraction_error",
                "detail": str(e),
            })
            continue
        except Exception as e:
            parse_failures.append({
                "candidate_id": cand_id,
                "file_name": pdf_path.name,
                "reason": "scanned_pdf_or_corrupt",
                "detail": str(e),
            })
            continue

        if not raw_text or len(raw_text) < 50:
            parse_failures.append({
                "candidate_id": cand_id,
                "file_name": pdf_path.name,
                "reason": "scanned_pdf_or_empty_text",
                "detail": f"Extracted text too short ({len(raw_text)} chars). Likely scanned or image-based PDF.",
            })
            continue

        # Check contamination
        is_syn = detect_synthetic_contamination(pdf_path, raw_text)
        if is_syn:
            synthetic_detected.add(pdf_path.name)

        # Step 2: Anonymization
        anon_text = anonymize_resume(raw_text, candidate_name=None, strip_institutions=True)

        # Step 3: Zero-PII check
        is_pii_clean, pii_leaks = verify_zero_pii_in_text(anon_text)

        # Step 4: Parse with deterministic rule mode (Taxonomy v2.1 FROZEN)
        parsed = parser_agent._parse_with_rules(anon_text)
        skills = parsed.skills or []
        total_skills_extracted += len(skills)

        # Step 5: Classify Role Family
        family = classify_resume_family(anon_text, skills)
        family_counts[family] = family_counts.get(family, 0) + 1

        is_in_scope = family in in_scope_families
        if is_in_scope:
            in_scope_count += 1
        else:
            out_of_scope_count += 1

        processed_candidates.append({
            "candidate_id": cand_id,
            "file_name": pdf_path.name,
            "role_family": family,
            "is_in_scope": is_in_scope,
            "out_of_scope_for_ranking_eval": not is_in_scope,
            "skills_count": len(skills),
            "skills": skills,
            "experience_count": len(parsed.experience or []),
            "pii_clean": is_pii_clean,
            "pii_leaks": pii_leaks,
            "extraction_engine": extraction_engine,
            "anonymized_text": anon_text,
        })

    # Contamination & Run-Type Gates (R16-1)
    n_total = len(pdf_files)
    n_syn = len(synthetic_detected)

    # 1. Refuse mixed real and synthetic folders across all run types
    if 0 < n_syn < n_total:
        raise ResumeContaminationError(
            f"CONTAMINATION ERROR: Mixed real and synthetic resumes detected in folder ({n_syn} synthetic, {n_total - n_syn} real). "
            "Mixing real and synthetic resumes is strictly prohibited across all run types."
        )

    # 2. run_type == 'real' strictly refuses synthetic resumes
    if run_type == "real" and n_syn > 0 and not allow_synthetic:
        raise ResumeContaminationError(
            f"CONTAMINATION ERROR: Synthetic resumes detected in real resume folder: {list(synthetic_detected)[:5]}... "
            "run_type='real' strictly prohibits synthetic resumes."
        )

    # 3. run_type == 'synthetic_eval' accepts SYN_ files ONLY
    if run_type == "synthetic_eval":
        if n_syn == 0:
            raise ResumeContaminationError(
                "REFUSAL: No synthetic resumes (SYN_) detected in folder for synthetic_eval run. "
                "synthetic_eval accepts SYN_ files ONLY."
            )
        if n_syn != n_total:
            raise ResumeContaminationError(
                f"CONTAMINATION ERROR: Folder contains non-synthetic resumes ({n_total - n_syn} non-synthetic). "
                "synthetic_eval accepts SYN_ files ONLY."
            )

    # Compute statistics
    n_successful = len(processed_candidates)
    avg_skills = round(float(total_skills_extracted / n_successful), 2) if n_successful > 0 else 0.0

    report = {
        "metadata": {
            "intake_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_type": run_type,
            "resumes_dir": str(in_dir).replace("\\", "/"),
            "output_dir": str(dest_dir).replace("\\", "/"),
            "git_commit": get_git_commit_hash(),
            "config_hash": get_file_sha256(FROZEN_CONFIG_PATH),
            "taxonomy_version": TAXONOMY_VERSION,
            "taxonomy_hash": get_taxonomy_sha256(),
        },
        "counts": {
            "total_files_inspected": len(pdf_files),
            "successfully_parsed": n_successful,
            "parse_failures": len(parse_failures),
            "in_scope_for_ranking": in_scope_count,
            "out_of_scope_deficit_families": out_of_scope_count,
        },
        "role_family_counts": family_counts,
        "average_skills_per_resume": avg_skills,
        "parse_failure_breakdown": parse_failures,
        "zero_pii_audit": {
            "all_resumes_pii_clean": all(c["pii_clean"] for c in processed_candidates),
            "total_leaks_detected": sum(len(c["pii_leaks"]) for c in processed_candidates),
        },
    }

    # Save intake report and processed candidates JSON (gitignored directory)
    report_file = dest_dir / "intake_report.json"
    candidates_file = dest_dir / "intake_candidates.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(candidates_file, "w", encoding="utf-8") as f:
        # Save anonymized candidate profiles without raw PII
        json.dump(processed_candidates, f, indent=2)

    print(f"\n================ RESUME INTAKE REPORT ({run_type.upper()}) ================")
    print(f"Total PDFs Inspected      : {len(pdf_files)}")
    print(f"Successfully Parsed       : {n_successful}")
    print(f"Parse Failures            : {len(parse_failures)}")
    print(f"In-Scope Candidates       : {in_scope_count}")
    print(f"Out-of-Scope Candidates   : {out_of_scope_count}")
    print(f"Average Skills / Resume   : {avg_skills}")
    print(f"Zero PII Audit            : {'PASSED (0 leaks)' if report['zero_pii_audit']['all_resumes_pii_clean'] else 'FAILED'}")
    print(f"Family Distribution       : {family_counts}")
    print(f"Saved Report to           : {report_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Real-resume Intake and Anonymization Processor")
    parser.add_argument("--resumes-dir", type=str, required=True, help="Path to resume PDF directory")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save report and anonymized profiles")
    parser.add_argument("--run-type", type=str, default="real", choices=["real", "synthetic_eval", "dryrun"], help="Run type guard")
    parser.add_argument("--allow-synthetic", action="store_true", help="Allow synthetic resumes (for test pipelines only)")
    args = parser.parse_args()

    process_resume_intake(
        resumes_dir=args.resumes_dir,
        output_dir=args.output_dir,
        run_type=args.run_type,
        allow_synthetic=args.allow_synthetic,
    )


if __name__ == "__main__":
    main()
