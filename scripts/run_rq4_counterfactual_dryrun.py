"""
scripts/run_rq4_counterfactual_dryrun.py
---------------------------------------
RQ4 Counterfactual evaluation (Remediation R13e):
- Evaluates 10 in-scope dry-run resumes with the frozen hybrid scorer.
- rank_gain = base_rank - new_rank (positive = job moves UP in rank towards 1).
- For each resume, picks a target job from candidate universe (ranked 2-10) with missing skills.
- Interventions:
  (a) Suggested skill: missing canonical skill required by target job.
  (b) Control skill: random same-family skill not in candidate resume or target job.
- Computes paired differences (suggested_gain - random_gain) across pairs.
- Paired bootstrap 95% CI with 10,000 resamples (seed 42).
- Pipeline check only; dryrun output.
"""

import copy
import csv
import json
from pathlib import Path
import random
import sys
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.hybrid import HybridRanker
from scripts.job_snapshot import load_snapshot


def run_rq4_counterfactual():
    # 1. Load intake candidates
    with open("results/dryrun/intake_candidates.json", "r", encoding="utf-8") as f:
        intake_list = json.load(f)
    records = {c["candidate_id"][:7]: c for c in intake_list}

    # 2. Load universes and snapshot
    with open("results/dryrun/candidate_universes.json", "r", encoding="utf-8") as f:
        univ_data = json.load(f)
    in_scope_u = univ_data["candidate_universes"]

    snapshot_records, _ = load_snapshot("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")
    job_map = {j["id"]: j for j in snapshot_records}

    # Select 10 in-scope candidate IDs
    cids = [f"SYN_{i:03d}" for i in range(1, 11) if f"SYN_{i:03d}" in in_scope_u]
    assert len(cids) == 10, f"Expected 10 in-scope resumes, got {len(cids)}"

    hybrid = HybridRanker()
    rng = random.Random(42)

    # Candidate same-family taxonomy skill pool (Data/AI)
    data_ai_skills = [
        "Python", "SQL", "Machine Learning", "Data Science", "Deep Learning",
        "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-Learn",
        "NLP", "Computer Vision", "Tableau", "Power BI", "Spark",
        "Statistics", "Big Data", "Data Engineering", "Data Analytics"
    ]

    pairs_data = []
    csv_rows = []

    for cid in cids:
        cand_rec = records[cid]
        univ_jids = in_scope_u[cid]["job_ids"]
        pool = [job_map[jid] for jid in univ_jids if jid in job_map]

        cand_resume = {
            "candidate_id": cid,
            "candidate_name": cand_rec.get("candidate_name") or cand_rec.get("candidate_id", cid),
            "skills": list(cand_rec.get("skills", [])),
            "summary": cand_rec.get("summary", ""),
            "raw_text": cand_rec.get("anonymized_text") or (cand_rec.get("summary", "") + " " + " ".join(cand_rec.get("skills", []))),
            "experience": cand_rec.get("experience", []),
        }

        # Baseline ranking
        base_res = hybrid.rank(cand_resume, pool, k=len(pool))
        base_rank_map = {jid: rank for rank, jid in enumerate(base_res.ranked_job_ids, start=1)}

        # Find target job in ranks 2..10 that has at least 1 missing skill
        target_job = None
        target_base_rank = None
        missing_skills = []

        cand_skills_lower = {s.lower() for s in cand_resume["skills"]}

        for r_jid in base_res.ranked_job_ids[1:10]:
            job = job_map[r_jid]
            j_skills = job.get("skills", [])
            m_skills = [s for s in j_skills if s.lower() not in cand_skills_lower]
            if m_skills:
                target_job = job
                target_base_rank = base_rank_map[r_jid]
                missing_skills = m_skills
                break

        if not target_job:
            # Fallback to rank 2
            target_job = job_map[base_res.ranked_job_ids[1]]
            target_base_rank = 2
            missing_skills = ["Machine Learning"]

        suggested_skill = missing_skills[0]

        # Select random control skill from same family not in resume and not in target job
        job_skills_lower = {s.lower() for s in target_job.get("skills", [])}
        eligible_controls = [
            s for s in data_ai_skills
            if s.lower() not in cand_skills_lower and s.lower() not in job_skills_lower
        ]
        control_skill = rng.choice(eligible_controls) if eligible_controls else "Tableau"

        # (a) Intervene with suggested skill
        cand_suggested = copy.deepcopy(cand_resume)
        cand_suggested["skills"].append(suggested_skill)
        cand_suggested["raw_text"] += f" {suggested_skill}"
        res_suggested = hybrid.rank(cand_suggested, pool, k=len(pool))
        new_rank_suggested = res_suggested.ranked_job_ids.index(target_job["id"]) + 1
        # Positive = job moves UP in rank towards 1
        gain_suggested = target_base_rank - new_rank_suggested

        # (b) Intervene with control skill
        cand_control = copy.deepcopy(cand_resume)
        cand_control["skills"].append(control_skill)
        cand_control["raw_text"] += f" {control_skill}"
        res_control = hybrid.rank(cand_control, pool, k=len(pool))
        new_rank_control = res_control.ranked_job_ids.index(target_job["id"]) + 1
        # Positive = job moves UP in rank towards 1
        gain_control = target_base_rank - new_rank_control

        paired_lift = gain_suggested - gain_control

        pairs_data.append({
            "candidate_id": cid,
            "target_job_id": target_job["id"],
            "target_title": target_job.get("title", ""),
            "target_base_rank": target_base_rank,
            "suggested_skill": suggested_skill,
            "new_rank_suggested": new_rank_suggested,
            "rank_gain_suggested": gain_suggested,
            "control_skill": control_skill,
            "new_rank_control": new_rank_control,
            "rank_gain_control": gain_control,
            "paired_lift": paired_lift,
        })

        csv_rows.append({
            "candidate_id": cid,
            "target_job_id": target_job["id"],
            "target_title": target_job.get("title", ""),
            "target_base_rank": target_base_rank,
            "suggested_skill": suggested_skill,
            "new_rank_suggested": new_rank_suggested,
            "rank_gain_suggested_positive_is_up": gain_suggested,
            "control_same_family_skill": control_skill,
            "new_rank_control": new_rank_control,
            "rank_gain_control_positive_is_up": gain_control,
            "paired_lift_suggested_minus_control": paired_lift,
        })

    # Paired Bootstrap 95% CI (10,000 resamples, seeded)
    n_pairs = len(pairs_data)
    lifts = np.array([p["paired_lift"] for p in pairs_data], dtype=float)
    suggested_gains = np.array([p["rank_gain_suggested"] for p in pairs_data], dtype=float)
    control_gains = np.array([p["rank_gain_control"] for p in pairs_data], dtype=float)

    mean_suggested_gain = float(np.mean(suggested_gains))
    mean_control_gain = float(np.mean(control_gains))
    mean_lift = float(np.mean(lifts))

    boot_rng = np.random.default_rng(42)
    boot_means = []
    for _ in range(10_000):
        sample = boot_rng.choice(lifts, size=n_pairs, replace=True)
        boot_means.append(float(np.mean(sample)))

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    out_csv = Path("results/dryrun/counterfactual_results_dryrun.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    summary = {
        "label": "pipeline check only (dry-run)",
        "n_pairs": n_pairs,
        "mean_rank_gain_suggested": round(mean_suggested_gain, 4),
        "mean_rank_gain_control": round(mean_control_gain, 4),
        "mean_paired_lift": round(mean_lift, 4),
        "bootstrap_95_ci": [round(ci_lower, 4), round(ci_upper, 4)],
        "bootstrap_resamples": 10000,
        "bootstrap_seed": 42,
        "historical_comparison": {
            "earlier_reported": "+1.89 [+1.00, +2.89], n=9",
            "verdict": "Unsupported on dryrun candidate corpus (new measured values reported).",
        },
        "pairs": pairs_data,
    }

    out_json = Path("results/dryrun/rq4_counterfactual_dryrun.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"=== RQ4 Counterfactual Results (Dry-run, Pipeline Check Only) ===")
    print(f"n pairs:                     {n_pairs}")
    print(f"Mean gain (suggested skill): {mean_suggested_gain:+.2f}")
    print(f"Mean gain (control skill):   {mean_control_gain:+.2f}")
    print(f"Mean paired lift:            {mean_lift:+.2f}")
    print(f"Paired Bootstrap 95% CI:     [{ci_lower:+.2f}, {ci_upper:+.2f}] (10,000 resamples, seed=42)")
    print(f"Saved JSON:                  {out_json}")
    print(f"Saved CSV:                   {out_csv}")


if __name__ == "__main__":
    run_rq4_counterfactual()
