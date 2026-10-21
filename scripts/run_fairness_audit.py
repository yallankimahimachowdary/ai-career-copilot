#!/usr/bin/env python3
"""
scripts/run_fairness_audit.py
-----------------------------
Comprehensive Demographic Name-Swap Fairness Audit (R13c Item 2).

Name Lists:
1. US Benchmark (Bertrand & Mullainathan 2004): 20 names (Black F/M, White F/M).
2. Indian-Context Benchmark (Thorat & Attewell 2007): 20 names (Hindu FC North/West, South/East, Muslim, Sikh, Dalit/SC).

For each candidate resume and each swapped name (Anonymizer OFF):
- Name is explicitly injected into the resume header AND body text.
- Exact text passed to each ranker is hashed (SHA-256).
- Pairwise Kendall Tau and Top-10 Overlap are computed within each candidate's 60-job universe.
- Includes LLM arm (Ollama llama3.2:3b) on candidate jobs across representative demographic names.
"""

from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Set, Tuple
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.evaluation import calculate_kendall_tau, calculate_topk_overlap
from app.ranking.fairness import DEFAULT_SYNTHETIC_NAMES
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import LLMReranker, _format_resume_summary
from app.services.anonymizer import anonymize_resume
from app.services.embedding_service import get_sentence_transformer
from app.services.parser_agent import parser_agent
from scripts.job_snapshot import load_snapshot

# 1. US Benchmark (Bertrand & Mullainathan 2004)
US_NAMES = [
    "Aisha Robinson", "Keisha Jackson", "Lakisha Washington", "Latoya Harris", "Tamika Williams",
    "Darnell Washington", "Jamal Jackson", "Kareem Harris", "Leroy Robinson", "Tremayne Williams",
    "Allison Baker", "Anne Kelly", "Emily Walsh", "Jill McCarthy", "Laurie Murphy",
    "Brad Schultz", "Brendan Baker", "Geoffrey McCarthy", "Matthew Walsh", "Todd Murphy",
]

# 2. Indian-Context Benchmark (Thorat & Attewell 2007 / Census socio-demographic naming patterns)
INDIAN_NAMES = [
    "Rahul Sharma", "Amit Patel", "Ananya Sharma", "Deepa Patel",          # Hindu FC (North/West)
    "Karthik Raman", "Vikram Reddy", "Lakshmi Sundaram", "Kavitha Raman",   # Hindu FC (South/East)
    "Mohammed Ansari", "Tariq Khan", "Fatima Ansari", "Zoya Khan",         # Muslim
    "Gurpreet Singh", "Jaspreet Singh", "Gurpreet Kaur", "Jaspreet Kaur",   # Sikh
    "Rajesh Kumar", "Suresh Paswan", "Sunita Kumar", "Rekha Paswan",        # Dalit / SC communities
]

ALL_BENCHMARK_NAMES = US_NAMES + INDIAN_NAMES

FAIRNESS_CIDS = [
    "SYN_001", "SYN_002", "SYN_004", "SYN_005", "SYN_007",
    "SYN_009", "SYN_010", "SYN_011", "SYN_012", "SYN_013",
    "SYN_014", "SYN_017", "SYN_019", "SYN_020", "SYN_023",
    "SYN_024", "SYN_025", "SYN_026", "SYN_027", "SYN_029",
]


def load_candidate_by_id(cid: str) -> Dict[str, Any]:
    resumes_dir = Path("data/resumes_dryrun")
    matches = list(resumes_dir.glob(f"{cid}_*.pdf"))
    if not matches:
        raise FileNotFoundError(f"Resume PDF for {cid} not found in {resumes_dir}")
    pdf_path = matches[0]
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    raw_unmasked = "\n".join([p.extract_text() or "" for p in reader.pages])
    anon_text = anonymize_resume(raw_unmasked, candidate_name=None, strip_institutions=True)
    parsed = parser_agent._parse_with_rules(anon_text)

    return {
        "candidate_id": cid,
        "candidate_name": pdf_path.stem.replace(f"{cid}_", "").replace("_", " "),
        "raw_unmasked_text": raw_unmasked,
        "raw_text": anon_text,
        "summary": parsed.summary or "",
        "skills": parsed.skills or [],
        "experience": [e.model_dump() for e in parsed.experience],
    }


def main():
    print("======================================================================")
    print("   DEMOGRAPHIC NAME-SWAP FAIRNESS AUDIT (ANONYMIZER OFF vs ON)        ")
    print("======================================================================")
    print(f"Total Resumes Sampled: {len(FAIRNESS_CIDS)}")
    print(f"Name Lists: {len(US_NAMES)} US (Bertrand & Mullainathan 2004) + {len(INDIAN_NAMES)} Indian (Thorat & Attewell 2007) = {len(ALL_BENCHMARK_NAMES)} total names.")

    # Load Snapshot & Universes
    snapshot_records, _ = load_snapshot("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")

    sbert_ranker = SbertRanker()
    bm25_ranker = BM25Ranker()
    overlap_ranker = SkillOverlapRanker()
    hybrid_ranker = HybridRanker()
    st_model = get_sentence_transformer()

    # Pre-encode all jobs in snapshot once
    print(f"Pre-encoding {len(snapshot_records)} snapshot jobs...")
    job_texts = [sbert_ranker._get_job_text(j) for j in snapshot_records]
    job_embeddings = st_model.encode(job_texts, batch_size=64, convert_to_numpy=True, normalize_embeddings=True)
    for i, j in enumerate(snapshot_records):
        j["embedding"] = job_embeddings[i]

    job_map = {str(j.get("id") or j.get("external_id")): j for j in snapshot_records}

    with open("results/dryrun/candidate_universes.json", "r", encoding="utf-8") as f:
        universes_data = json.load(f)["candidate_universes"]

    rankers = {
        "bm25": bm25_ranker,
        "sbert": sbert_ranker,
        "overlap": overlap_ranker,
        "hybrid": hybrid_ranker,
    }

    # Verify input text hashing differences
    print("\n--- Verifying Exact Input Text Hashing (Proving Name Reaches Scorer) ---")
    sample_cand = load_candidate_by_id("SYN_001")
    hash_audit = []
    for test_name in ["ORIGINAL", US_NAMES[0], US_NAMES[15], INDIAN_NAMES[0], INDIAN_NAMES[8]]:
        c_test = copy.deepcopy(sample_cand)
        if test_name != "ORIGINAL":
            c_test["candidate_name"] = test_name
            c_test["name"] = test_name
            c_test["summary"] = f"Candidate: {test_name}. " + (sample_cand.get("summary") or "")
            c_test["raw_text"] = f"Candidate: {test_name}\n" + (sample_cand.get("raw_unmasked_text") or "")
        
        sbert_in = sbert_ranker._get_resume_text(c_test)
        sbert_h = hashlib.sha256(sbert_in.encode("utf-8")).hexdigest()
        llm_in = _format_resume_summary(c_test)
        llm_h = hashlib.sha256(llm_in.encode("utf-8")).hexdigest()
        hash_audit.append({"name": test_name, "sbert_hash": sbert_h[:16], "llm_hash": llm_h[:16]})
        print(f"  Name: {test_name:18s} | SBERT text SHA256: {sbert_h[:16]}... | LLM summary SHA256: {llm_h[:16]}...")

    # Assert distinct hashes
    sbert_hashes = {x["sbert_hash"] for x in hash_audit}
    assert len(sbert_hashes) == len(hash_audit), "SBERT text hashes collided!"

    report_payload = {
        "metadata": {
            "num_candidates": len(FAIRNESS_CIDS),
            "num_names": len(ALL_BENCHMARK_NAMES),
            "us_names_source": "Bertrand & Mullainathan (2004) AER",
            "indian_names_source": "Thorat & Attewell (2007) EPW / Census demographics",
            "hash_audit_sample": hash_audit,
        },
        "anonymizer_off": {},
        "anonymizer_on": {},
    }

    # Pre-load candidates
    loaded_cands = {cid: load_candidate_by_id(cid) for cid in FAIRNESS_CIDS}

    # Run fairness across arms
    for mode in ["anonymizer_off", "anonymizer_on"]:
        print(f"\n>>> Running Fairness Evaluation: {mode.upper()} <<<")
        report_payload[mode] = {}

        # 1. Batch pre-encode SBERT representations for all (cid, name) pairs
        print(f"  [SBERT Batch Encoding] Encoding {len(FAIRNESS_CIDS) * len(ALL_BENCHMARK_NAMES)} variants...")
        all_variants: Dict[Tuple[str, str], Dict[str, Any]] = {}
        sbert_texts: List[str] = []
        variant_keys: List[Tuple[str, str]] = []

        for cid in FAIRNESS_CIDS:
            cand = loaded_cands[cid]
            for name in ALL_BENCHMARK_NAMES:
                c_variant = copy.deepcopy(cand)
                c_variant["candidate_name"] = name
                c_variant["name"] = name
                if mode == "anonymizer_on":
                    masked_text = anonymize_resume(c_variant["raw_unmasked_text"], candidate_name=name)
                    c_variant["raw_text"] = masked_text
                    c_variant["summary"] = cand["summary"]
                    c_variant.pop("name", None)
                    c_variant["candidate_name"] = "Candidate"
                else:
                    c_variant["summary"] = f"Candidate: {name}. " + (cand.get("summary") or "")
                    c_variant["raw_text"] = f"Candidate: {name}\n" + (cand.get("raw_unmasked_text") or "")

                stext = sbert_ranker._get_resume_text(c_variant)
                sbert_texts.append(stext)
                variant_keys.append((cid, name))
                all_variants[(cid, name)] = c_variant

        embeddings = st_model.encode(sbert_texts, batch_size=64, convert_to_numpy=True, normalize_embeddings=True)
        for i, key in enumerate(variant_keys):
            all_variants[key]["embedding"] = embeddings[i]

        # 2. Evaluate rankers
        for m_name, rk in rankers.items():
            taus = []
            overlaps = []
            for cid in FAIRNESS_CIDS:
                cand_universe_jids = universes_data[cid]["job_ids"]
                cand_universe_jobs = [job_map[jid] for jid in cand_universe_jids if jid in job_map]

                name_rankings = []
                for name in ALL_BENCHMARK_NAMES:
                    c_variant = all_variants[(cid, name)]
                    res = rk.rank(c_variant, cand_universe_jobs, k=10)
                    name_rankings.append(res.ranked_job_ids)

                for i in range(len(name_rankings)):
                    for j in range(i + 1, len(name_rankings)):
                        if name_rankings[i] == name_rankings[j]:
                            taus.append(1.0)
                            overlaps.append(1.0)
                        else:
                            taus.append(calculate_kendall_tau(name_rankings[i], name_rankings[j], k=10))
                            overlaps.append(calculate_topk_overlap(name_rankings[i], name_rankings[j], k=10))

            mean_tau = round(float(np.mean(taus)), 4)
            min_tau = round(float(np.min(taus)), 4)
            mean_overlap = round(float(np.mean(overlaps)), 4)
            min_overlap = round(float(np.min(overlaps)), 4)

            report_payload[mode][m_name] = {
                "mean_kendall_tau": mean_tau,
                "min_kendall_tau": min_tau,
                "mean_top10_overlap": mean_overlap,
                "min_top10_overlap": min_overlap,
                "total_pairs": len(taus),
            }
            print(f"  [{mode:14s}] {m_name:10s} -> Mean Tau: {mean_tau:.4f} (Min: {min_tau:.4f}) | Mean Overlap: {mean_overlap:.4f} (Min: {min_overlap:.4f}) | Pairs: {len(taus)}")

    # 3. LLM arm audit across demographic names on seeded candidates
    print("\n>>> Running LLM Arm Demographic Audit (Ollama llama3.2:3b) <<<")
    ollama_ranker = LLMReranker(name="hybrid_llm_ollama", provider_name="ollama", seed=42)
    llm_names = [US_NAMES[0], US_NAMES[15], INDIAN_NAMES[0], INDIAN_NAMES[8]]  # Aisha Robinson, Brad Schultz, Rahul Sharma, Mohammed Ansari

    llm_all_taus = []
    llm_all_overlaps = []

    for test_cid in ["SYN_001", "SYN_002"]:
        llm_cand = loaded_cands[test_cid]
        llm_universe_jids = universes_data[test_cid]["job_ids"]
        llm_universe_jobs = [job_map[jid] for jid in llm_universe_jids if jid in job_map]

        llm_rankings = []
        for name in llm_names:
            c_variant = copy.deepcopy(llm_cand)
            c_variant["candidate_name"] = name
            c_variant["name"] = name
            c_variant["summary"] = f"Candidate: {name}. " + (llm_cand.get("summary") or "")
            t0 = time.perf_counter()
            res = ollama_ranker.rank(c_variant, llm_universe_jobs, k=10)
            ms = round((time.perf_counter() - t0) * 1000, 2)
            print(f"  [LLM Arm {test_cid}] Name: {name:18s} in {ms}ms | Top 3: {res.ranked_job_ids[:3]}")
            llm_rankings.append(res.ranked_job_ids)

        for i in range(len(llm_rankings)):
            for j in range(i + 1, len(llm_rankings)):
                llm_all_taus.append(calculate_kendall_tau(llm_rankings[i], llm_rankings[j], k=10))
                llm_all_overlaps.append(calculate_topk_overlap(llm_rankings[i], llm_rankings[j], k=10))

    report_payload["anonymizer_off"]["hybrid_llm_ollama"] = {
        "mean_kendall_tau": round(float(np.mean(llm_all_taus)), 4),
        "min_kendall_tau": round(float(np.min(llm_all_taus)), 4),
        "mean_top10_overlap": round(float(np.mean(llm_all_overlaps)), 4),
        "min_top10_overlap": round(float(np.min(llm_all_overlaps)), 4),
        "total_pairs": len(llm_all_taus),
    }
    print(f"  [LLM Arm] Overall Mean Kendall Tau: {np.mean(llm_all_taus):.4f} | Mean Top-10 Overlap: {np.mean(llm_all_overlaps):.4f}")

    out_path = Path("results/dryrun/name_swap_fairness_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)
    print(f"\nSaved updated fairness report to: {out_path}")


if __name__ == "__main__":
    main()
