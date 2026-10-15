import dataclasses
import json
from pathlib import Path
from app.ranking.claim_verifier import ClaimVerifier
from scripts.job_snapshot import load_snapshot
from scripts.run_ranking_experiment import load_and_anonymize_resumes

def audit_b5():
    print("=== B5: Claim Verifier Audit over B4 Real LLM Explanations ===")
    snapshot_records, _ = load_snapshot("data/snapshots/test_snap_1.json")
    jobs_map = {str(r.get("id") or r.get("external_id")): r for r in snapshot_records}
    resumes = load_and_anonymize_resumes("uploads/resumes")
    resume_map = {r["candidate_name"]: r for r in resumes}

    with open("artifacts/audit/b4_reranker_verification.json", "r", encoding="utf-8") as f:
        b4_data = json.load(f)

    verifier = ClaimVerifier()
    audit_results = {}

    for provider in ["ollama", "gemini"]:
        print(f"\n================ Provider: {provider.upper()} ================")
        audit_results[provider] = {}

        for cand_name in ["Deepika", "Mahima"]:
            c_data = b4_data[provider][cand_name]
            explanations = c_data["explanations"]
            resume = resume_map[cand_name]

            verifications, mean_score = verifier.verify_all(explanations, resume, jobs_map)
            print(f"\n--- {cand_name} (Mean Faithfulness: {mean_score:.4f}) ---")
            print(f"Total Explanations Evaluated: {len(verifications)}")

            cand_audit = []
            for v in verifications:
                print(f"Rank {v.rank:2d} | Job: {v.job_id[:8]}.. | Faithfulness: {v.faithfulness_score:.2f} | Supported: {v.supported_claims}/{v.total_claims}")
                if v.invalid_matched:
                    print(f"    - Invalid Matched: {v.invalid_matched}")
                if v.invalid_missing:
                    print(f"    - Invalid Missing: {v.invalid_missing}")
                if v.unsupported_reason_skills:
                    print(f"    - Unsupported in Reason: {v.unsupported_reason_skills}")

                cand_audit.append(dataclasses.asdict(v))

            audit_results[provider][cand_name] = {
                "mean_faithfulness": round(mean_score, 4),
                "total_explanations": len(verifications),
                "verifications": cand_audit,
            }

    out_file = Path("artifacts/audit/b5_claim_verifier_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)

    print(f"\nSaved fresh B5 verifier results to {out_file}")

if __name__ == "__main__":
    audit_b5()
