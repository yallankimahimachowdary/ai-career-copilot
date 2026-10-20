#!/usr/bin/env python3
"""
scripts/eval_parser.py
----------------------
Parser Evaluation and Skill Vocabulary Benchmark (R11-4).

Capabilities:
1. Evaluates parser extracted skills against gold skill annotations (.jsonl or .json).
2. Computes both micro-averaged and macro-averaged (per-resume mean) Precision, Recall, and F1.
3. Computes 95% bootstrap confidence intervals (1,000 resamples, seeded).
4. Generates an unanchored, blank gold-template CSV for a seeded sample of 25 resumes
   stratified by role family (strictly blank of predictions to prevent anchoring bias).
"""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pypdf

from app.core.taxonomy import extract_canonical_skills
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent
from scripts.check_dataset_overlap import ROLE_FAMILIES


def compute_prf1(predicted: Set[str], gold: Set[str]) -> Tuple[float, float, float]:
    """Calculate Precision, Recall, and F1 given two sets of lower-cased skill tokens."""
    if not predicted and not gold:
        return 1.0, 1.0, 1.0
    if not predicted or not gold:
        return 0.0, 0.0, 0.0

    tp = len(predicted.intersection(gold))
    precision = tp / len(predicted) if len(predicted) > 0 else 0.0
    recall = tp / len(gold) if len(gold) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def bootstrap_prf1_ci(
    per_resume_metrics: List[Dict[str, float]],
    n_resamples: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> Dict[str, Tuple[float, float]]:
    """Compute bootstrap confidence intervals for micro and macro F1."""
    if not per_resume_metrics:
        return {"macro_f1": (0.0, 0.0), "micro_f1": (0.0, 0.0)}

    rng = random.Random(seed)
    n = len(per_resume_metrics)
    macro_f1s = []
    micro_f1s = []

    indices = list(range(n))
    for _ in range(n_resamples):
        sample_idx = [rng.choice(indices) for _ in range(n)]
        
        # Macro calculation
        sample_f1s = [per_resume_metrics[i]["f1"] for i in sample_idx]
        macro_f1s.append(sum(sample_f1s) / len(sample_f1s))

        # Micro calculation
        total_tp = sum(per_resume_metrics[i]["tp"] for i in sample_idx)
        total_pred = sum(per_resume_metrics[i]["pred_count"] for i in sample_idx)
        total_gold = sum(per_resume_metrics[i]["gold_count"] for i in sample_idx)

        prec = total_tp / total_pred if total_pred > 0 else 0.0
        rec = total_tp / total_gold if total_gold > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        micro_f1s.append(f1)

    macro_f1s.sort()
    micro_f1s.sort()

    low_idx = int(n_resamples * (alpha / 2.0))
    high_idx = int(n_resamples * (1.0 - alpha / 2.0))

    return {
        "macro_f1": (round(macro_f1s[low_idx], 4), round(macro_f1s[min(high_idx, n_resamples - 1)], 4)),
        "micro_f1": (round(micro_f1s[low_idx], 4), round(micro_f1s[min(high_idx, n_resamples - 1)], 4)),
    }


def load_gold_annotations(gold_path: Path | str) -> List[Dict[str, Any]]:
    """Load gold skill annotations from either JSONL or JSON format."""
    p = Path(gold_path)
    if not p.exists():
        raise FileNotFoundError(f"Gold annotation file not found: {p}")

    entries = []
    if p.suffix == ".jsonl":
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    else:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data.get("resumes", []) if isinstance(data, dict) else data

    # Normalize entries to {resume_id, skills}
    normalized = []
    for e in entries:
        rid = e.get("resume_id") or e.get("resume_file") or e.get("id") or ""
        skills = e.get("skills", [])
        name = e.get("candidate_name")
        normalized.append({
            "resume_id": rid,
            "skills": [s.strip() for s in skills if isinstance(s, str) and s.strip()],
            "candidate_name": name,
        })
    return normalized


def evaluate_parser(
    gold_file_path: Path | str = "data/gold/gold_resumes_skills.json",
    resumes_dir: Path | str = "data/resumes_dryrun",
    seed: int = 42,
) -> Dict[str, Any]:
    """Run parser evaluation on all entries defined in the gold JSON/JSONL file."""
    gold_entries = load_gold_annotations(gold_file_path)
    resumes_path = Path(resumes_dir)

    results: List[Dict[str, Any]] = []
    sample_for_ci: List[Dict[str, float]] = []

    total_tp = 0
    total_pred = 0
    total_gold = 0

    for entry in gold_entries:
        rid = entry["resume_id"]
        gold_skills = {s.strip().lower() for s in entry["skills"]}
        
        # Locate target file
        target_path = Path(rid)
        if not target_path.exists():
            target_path = resumes_path / Path(rid).name
        if not target_path.exists():
            matches = list(resumes_path.glob(f"{Path(rid).stem}*"))
            if matches:
                target_path = matches[0]

        if not target_path.exists():
            print(f"[WARN] Resume file not found: {rid}. Skipping.")
            continue

        name_hint = entry.get("candidate_name")
        try:
            reader = pypdf.PdfReader(target_path)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            raw = ""

        anon_text = anonymize_resume(raw, candidate_name=name_hint, strip_institutions=True)
        parsed = parser_agent._parse_with_rules(anon_text)

        extracted = {s.strip().lower() for s in (parsed.skills or [])}
        extracted.update(s.lower() for s in extract_canonical_skills(anon_text))

        prec, rec, f1 = compute_prf1(extracted, gold_skills)

        tp = len(extracted.intersection(gold_skills))
        total_tp += tp
        total_pred += len(extracted)
        total_gold += len(gold_skills)

        sample_for_ci.append({
            "tp": float(tp),
            "pred_count": float(len(extracted)),
            "gold_count": float(len(gold_skills)),
            "precision": prec,
            "recall": rec,
            "f1": f1,
        })

        results.append({
            "resume_id": rid,
            "file_name": target_path.name,
            "gold_count": len(gold_skills),
            "predicted_count": len(extracted),
            "true_positives": tp,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "missed_skills": sorted(list(gold_skills - extracted)),
            "false_positive_skills": sorted(list(extracted - gold_skills)),
        })

    # Micro averages
    micro_prec = round(total_tp / total_pred, 4) if total_pred > 0 else 0.0
    micro_rec = round(total_tp / total_gold, 4) if total_gold > 0 else 0.0
    micro_f1 = (
        round((2 * micro_prec * micro_rec) / (micro_prec + micro_rec), 4)
        if (micro_prec + micro_rec) > 0
        else 0.0
    )

    # Macro averages
    macro_prec = round(sum(r["precision"] for r in results) / len(results), 4) if results else 0.0
    macro_rec = round(sum(r["recall"] for r in results) / len(results), 4) if results else 0.0
    macro_f1 = round(sum(r["f1"] for r in results) / len(results), 4) if results else 0.0

    # Confidence intervals
    cis = bootstrap_prf1_ci(sample_for_ci, n_resamples=1000, seed=seed)

    summary = {
        "total_resumes_evaluated": len(results),
        "micro_metrics": {
            "precision": micro_prec,
            "recall": micro_rec,
            "f1": micro_f1,
            "f1_95_ci": list(cis["micro_f1"]),
        },
        "macro_metrics": {
            "precision": macro_prec,
            "recall": macro_rec,
            "f1": macro_f1,
            "f1_95_ci": list(cis["macro_f1"]),
        },
        "per_resume_results": results,
    }
    return summary


def generate_gold_template_csv(
    resumes_dir: Path | str,
    output_csv_path: Path | str,
    sample_size: int = 25,
    seed: int = 42,
) -> Dict[str, Any]:
    """Generate an unanchored, blank gold-standard template CSV for 25 resumes stratified by family."""
    rng = random.Random(seed)
    res_d = Path(resumes_dir)
    pdf_files = sorted(list(res_d.glob("*.pdf")))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF resumes found in {res_d}")

    # Group by role family
    by_family: Dict[str, List[Path]] = defaultdict(list)
    for pdf in pdf_files:
        try:
            reader = pypdf.PdfReader(pdf)
            txt = (reader.pages[0].extract_text() or "").lower() if reader.pages else ""
        except Exception:
            txt = ""

        fam_match = "Web/Software"
        for fam, kws in ROLE_FAMILIES.items():
            if any(kw in txt for kw in kws):
                fam_match = fam
                break
        by_family[fam_match].append(pdf)

    # Stratified selection of 25 resumes
    selected_files: List[Tuple[str, Path]] = []
    fam_names = sorted(by_family.keys())

    # Proportional sampling
    total_files = len(pdf_files)
    n_target = min(sample_size, total_files)
    slots_left = n_target

    for fam in fam_names:
        pool = list(by_family[fam])
        rng.shuffle(pool)
        n_take = max(1, int((len(pool) / total_files) * n_target))
        n_take = min(n_take, len(pool), slots_left)
        for f in pool[:n_take]:
            selected_files.append((fam, f))
        slots_left -= n_take

    # Fill remainder if slots left
    if slots_left > 0:
        remainder_pool = [
            (fam, f) for fam in fam_names for f in by_family[fam]
            if (fam, f) not in selected_files
        ]
        rng.shuffle(remainder_pool)
        selected_files.extend(remainder_pool[:slots_left])

    selected_files = selected_files[:sample_size]
    # Sort deterministically by file name
    selected_files.sort(key=lambda x: x[1].name)

    out_p = Path(output_csv_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for fam, pdf_path in selected_files:
        try:
            reader = pypdf.PdfReader(pdf_path)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            raw = ""

        # Mask PII / academic institutions
        anon = anonymize_resume(raw, strip_institutions=True)
        # Format compact snippet for annotator inspection
        snippet = re.sub(r"\s+", " ", anon)[:600]

        parts = pdf_path.stem.split("_")
        cid = f"{parts[0]}_{parts[1]}" if len(parts) > 1 and parts[0] == "SYN" else parts[0]

        rows.append({
            "resume_id": cid,
            "role_family": fam,
            "resume_file": pdf_path.name,
            "resume_text_excerpt": snippet,
            "gold_skills_comma_separated": "",  # Strictly BLANK
        })

    with open(out_p, "w", encoding="utf-8", newline="") as f:
        f.write("# GOLD SKILLS ANNOTATION TEMPLATE (UNANCHORED PROTOCOL)\n")
        f.write("# Instructions: Read the resume excerpt and enter canonical technical skills separated by commas.\n")
        f.write("# To prevent anchoring bias, this template contains ZERO model predictions or suggested tags.\n")
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "resume_id",
                "role_family",
                "resume_file",
                "resume_text_excerpt",
                "gold_skills_comma_separated",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return {
        "total_resumes_sampled": len(rows),
        "families_represented": sorted(list({r["role_family"] for r in rows})),
        "template_output_path": str(out_p),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Resume Parser or Generate Gold Template")
    parser.add_argument("--gold", type=str, default="data/gold/gold_resumes_skills.json", help="Path to gold annotations (.json or .jsonl)")
    parser.add_argument("--resumes", type=str, default="data/resumes_dryrun", help="Path to resumes folder")
    parser.add_argument("--generate-template", type=str, default=None, help="Generate blank gold CSV template to target path")
    parser.add_argument("--sample-size", type=int, default=25, help="Sample size for gold template")
    parser.add_argument("--seed", type=int, default=42, help="Seed for template sampling")

    args = parser.parse_args()

    if args.generate_template:
        res = generate_gold_template_csv(
            resumes_dir=args.resumes,
            output_csv_path=args.generate_template,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        print(f"Generated blank gold template with {res['total_resumes_sampled']} resumes across {len(res['families_represented'])} families.")
        print(f"Saved to: {res['template_output_path']}")
        return

    report = evaluate_parser(gold_file_path=args.gold, resumes_dir=args.resumes, seed=args.seed)
    print("\n================ Parser Evaluation Summary (R11-4) ================")
    print(f"Resumes Evaluated : {report['total_resumes_evaluated']}")
    print(f"Micro Precision   : {report['micro_metrics']['precision']:.4f}")
    print(f"Micro Recall      : {report['micro_metrics']['recall']:.4f}")
    print(f"Micro F1 Score    : {report['micro_metrics']['f1']:.4f} (95% CI: {report['micro_metrics']['f1_95_ci']})")
    print(f"Macro F1 Score    : {report['macro_metrics']['f1']:.4f} (95% CI: {report['macro_metrics']['f1_95_ci']})")


if __name__ == "__main__":
    main()
