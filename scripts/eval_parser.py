"""
scripts/eval_parser.py
----------------------
Parser Evaluation and Skill Vocabulary Benchmark (Phase B8):
Compares the parser's extracted skills against hand-labeled gold skill files.
Calculates and reports Precision, Recall, and F1 per resume and overall.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pypdf

from app.core.taxonomy import extract_canonical_skills
from app.services.anonymizer import anonymize_resume
from app.services.parser_agent import parser_agent


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


def evaluate_parser(gold_file_path: Path | str) -> Dict[str, Any]:
    """Run parser evaluation on all entries defined in the gold JSON file."""
    gold_path = Path(gold_file_path)
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold annotation file not found: {gold_path}")

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    entries = gold_data.get("resumes", [])
    results: List[Dict[str, Any]] = []

    total_tp = 0
    total_pred = 0
    total_gold = 0

    for entry in entries:
        r_file = entry.get("resume_file")
        gold_skills = {s.strip().lower() for s in entry.get("skills", [])}
        target_path = Path(r_file)

        if not target_path.exists():
            # Try looking inside uploads/resumes/
            target_path = Path("uploads/resumes") / Path(r_file).name

        if not target_path.exists():
            # Try globbing by stem prefix
            prefix = Path(r_file).name.split("_")[0]
            matches = list(Path("uploads/resumes").glob(f"{prefix}*"))
            if matches:
                target_path = matches[0]

        if not target_path.exists():
            print(f"[WARN] Resume file not found: {r_file}. Skipping.")
            continue

        name_hint = "Mahima" if "Mahima" in target_path.name else ("Deepika" if "Deepika" in target_path.name else None)
        try:
            reader = pypdf.PdfReader(target_path)
            raw = "\n".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            raw = ""

        anon_text = anonymize_resume(raw, candidate_name=name_hint)
        parsed = parser_agent._parse_with_rules(anon_text)

        # Normalize extracted skills canonically
        extracted = {s.strip().lower() for s in (parsed.skills or [])}
        extracted.update(s.lower() for s in extract_canonical_skills(anon_text))

        prec, rec, f1 = compute_prf1(extracted, gold_skills)

        tp = len(extracted.intersection(gold_skills))
        total_tp += tp
        total_pred += len(extracted)
        total_gold += len(gold_skills)

        results.append({
            "resume_file": target_path.name,
            "gold_count": len(gold_skills),
            "predicted_count": len(extracted),
            "true_positives": tp,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "missed_skills": sorted(list(gold_skills - extracted)),
            "false_positive_skills": sorted(list(extracted - gold_skills)),
        })

    overall_prec = round(total_tp / total_pred, 4) if total_pred > 0 else 0.0
    overall_rec = round(total_tp / total_gold, 4) if total_gold > 0 else 0.0
    overall_f1 = (
        round((2 * overall_prec * overall_rec) / (overall_prec + overall_rec), 4)
        if (overall_prec + overall_rec) > 0
        else 0.0
    )

    summary = {
        "overall_precision": overall_prec,
        "overall_recall": overall_rec,
        "overall_f1": overall_f1,
        "total_resumes": len(results),
        "per_resume_results": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate Resume Parser against Gold File")
    parser.add_argument("--gold", type=str, default="data/gold/gold_resumes_skills.json", help="Path to gold JSON annotations")
    args = parser.parse_args()

    report = evaluate_parser(args.gold)
    print("\n================ Parser Evaluation Summary (Phase B8) ================")
    print(f"Overall Precision : {report['overall_precision']:.4f}")
    print(f"Overall Recall    : {report['overall_recall']:.4f}")
    print(f"Overall F1 Score  : {report['overall_f1']:.4f}")
    print(f"Total Evaluated   : {report['total_resumes']}")
    print("\nPer-Resume Breakdown:")
    for r in report["per_resume_results"]:
        print(f"\n--- Resume: {r['resume_file']} ---")
        print(f"Metrics: Precision={r['precision']:.4f}, Recall={r['recall']:.4f}, F1={r['f1']:.4f}")
        print(f"Gold Count: {r['gold_count']} | Predicted Count: {r['predicted_count']} | True Positives: {r['true_positives']}")
        print(f"False Positives (Predicted but NOT in Gold - lowers precision) [{len(r['false_positive_skills'])}]:")
        for fp in r['false_positive_skills']:
            print(f"   + {fp}")
        print(f"False Negatives (In Gold but MISSED by Parser - lowers recall) [{len(r['missed_skills'])}]:")
        for fn in r['missed_skills']:
            print(f"   - {fn}")


if __name__ == "__main__":
    main()
