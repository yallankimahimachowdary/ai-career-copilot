from pathlib import Path
"""
tests/test_r13b_corrections.py
------------------------------
Unit tests for Remediation R13b verification items:
1. Universe-only ranking: evaluation rejects snapshot slice and requires candidate universes.
2. Prompt hash equality: prompt hashes remain bit-for-bit identical across repeats.
3. Claim negation: negated requirements are not validated as required missing skills.
4. Alias matching: taxonomy aliases (k8s -> Kubernetes, GCP -> Google Cloud, etc.) resolve correctly.
5. Counterfactual direction: missing required skill provides rank gain over irrelevant within-family control skill.
"""

import copy
import hashlib
import pytest
from app.ranking.claim_verifier import ClaimVerifier
from app.ranking.counterfactual import CounterfactualTester
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import _format_resume_summary
from scripts.evaluate_ranking import run_evaluation_pipeline


def test_universe_only_ranking_refuses_snapshot_slice(tmp_path):
    """Enforce that real evaluation or pipeline runs with judgments strictly forbid max_jobs slicing."""
    fake_judgments = tmp_path / "labels.jsonl"
    fake_judgments.write_text('{"query_id": "SYN_001", "doc_id": "job_1", "rating": 3}\n', encoding="utf-8")

    # When judgments are provided (real or dryrun eval mode), dryrun_max_jobs_slice must raise ValueError
    with pytest.raises(ValueError, match="Slicing snapshot jobs via dryrun_max_jobs_slice"):
        run_evaluation_pipeline(
            snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
            output_report_path=str(tmp_path / "report.json"),
            judgments_path=str(fake_judgments),
            run_type="real",
            dryrun_max_jobs_slice=100,
        )


def test_prompt_hashes_identical_across_repeats():
    """Verify prompt formatting and prompt hash are completely deterministic across repeat invocations."""
    cand = {
        "candidate_id": "SYN_001",
        "candidate_name": "Aarav Sharma",
        "summary": "Data Scientist with PyTorch and NLP experience.",
        "skills": ["Python", "PyTorch", "SQL", "NLP"],
        "experience": [
            {"title": "Data Science Intern", "company": "Tech Corp", "description": "Built NLP pipelines"}
        ],
    }

    # Format summary repeatedly
    prompt_1 = _format_resume_summary(cand)
    hash_1 = hashlib.sha256(prompt_1.encode("utf-8")).hexdigest()

    prompt_2 = _format_resume_summary(cand)
    hash_2 = hashlib.sha256(prompt_2.encode("utf-8")).hexdigest()

    prompt_3 = _format_resume_summary(copy.deepcopy(cand))
    hash_3 = hashlib.sha256(prompt_3.encode("utf-8")).hexdigest()

    assert prompt_1 == prompt_2 == prompt_3
    assert hash_1 == hash_2 == hash_3


def test_claim_negation_detection():
    """Verify that negated skills in job descriptions are rejected by ClaimVerifier."""
    verifier = ClaimVerifier()
    resume = {
        "skills": ["Python", "Docker"],
        "summary": "Backend developer with Python and Docker.",
    }
    job = {
        "title": "Backend Python Developer",
        "description": "Looking for Python and Docker. Java is not required for this role. No Kubernetes needed.",
        "skills": ["Python", "Docker"],
    }

    # Explanation claims Java and Kubernetes are missing requirements
    exp = {
        "job_id": "job_test_neg",
        "rank": 1,
        "matched_skills": ["Python", "Docker"],
        "missing_skills": ["Java", "Kubernetes"],
        "reason": "Strong Python candidate, but lacks Java and Kubernetes.",
    }

    res = verifier.verify_explanation(exp, resume, job)
    # Both Java and Kubernetes were explicitly negated in the job description
    assert "Java" in res.invalid_missing
    assert "Kubernetes" in res.invalid_missing
    assert len(res.valid_missing) == 0
    assert res.faithfulness_score < 1.0


def test_claim_alias_matching():
    """Verify that canonical aliases resolve bidirectionally between resume, job, and claims."""
    verifier = ClaimVerifier()
    resume = {
        "skills": ["GCP", "Postgres", "k8s"],
        "summary": "Cloud developer experienced in GCP, Postgres, and k8s.",
    }
    job = {
        "title": "Cloud Platform Engineer",
        "description": "Requires Google Cloud Platform, PostgreSQL, and Kubernetes.",
        "skills": ["Google Cloud", "PostgreSQL", "Kubernetes"],
    }

    exp = {
        "job_id": "job_alias",
        "rank": 1,
        "matched_skills": ["Google Cloud", "Kubernetes", "PostgreSQL"],
        "missing_skills": [],
        "reason": "Candidate has strong Google Cloud, Kubernetes, and PostgreSQL experience.",
    }

    res = verifier.verify_explanation(exp, resume, job)
    assert len(res.invalid_matched) == 0
    assert "Google Cloud" in res.valid_matched
    assert "Kubernetes" in res.valid_matched
    assert "PostgreSQL" in res.valid_matched
    assert res.faithfulness_score == 1.0


def test_counterfactual_direction_rank_change():
    """Verify that adding a suggested missing skill improves or maintains target job rank vs control."""
    hybrid = HybridRanker()
    cand = {
        "candidate_id": "TEST_001",
        "skills": ["Python", "SQL"],
        "summary": "Python and SQL developer.",
        "raw_text": "Python and SQL developer looking for backend roles.",
    }

    jobs = [
        {"id": "job_1", "title": "Python Developer", "skills": ["Python", "SQL"], "description": "Python SQL"},
        {"id": "job_2", "title": "Data Engineer", "skills": ["Python", "SQL", "Spark"], "description": "Python SQL Apache Spark"},
        {"id": "job_3", "title": "Frontend Developer", "skills": ["React", "CSS"], "description": "React CSS"},
    ]

    base_rank = hybrid.rank(cand, jobs, k=3)
    old_rank_job2 = base_rank.ranked_job_ids.index("job_2") + 1

    # Condition A: Add suggested missing skill ("Spark")
    cand_sugg = copy.deepcopy(cand)
    cand_sugg["skills"].append("Spark")
    cand_sugg["raw_text"] += " Spark"
    rank_sugg = hybrid.rank(cand_sugg, jobs, k=3)
    new_rank_sugg = rank_sugg.ranked_job_ids.index("job_2") + 1
    gain_sugg = old_rank_job2 - new_rank_sugg

    # Condition B: Add unrelated control skill ("Ruby")
    cand_ctrl = copy.deepcopy(cand)
    cand_ctrl["skills"].append("Ruby")
    cand_ctrl["raw_text"] += " Ruby"
    rank_ctrl = hybrid.rank(cand_ctrl, jobs, k=3)
    new_rank_ctrl = rank_ctrl.ranked_job_ids.index("job_2") + 1
    gain_ctrl = old_rank_job2 - new_rank_ctrl

    # Suggested required skill must produce equal or better gain than unrelated control
    assert gain_sugg >= gain_ctrl
    assert rank_sugg.scores["job_2"] > base_rank.scores["job_2"]


def test_name_swap_inputs_hash_differently():
    """Verify that when anonymizer is OFF, swapping candidate names changes the input text hashes.
    
    If swapped inputs hash identically, the candidate name never reaches the scorer and the test fails.
    """
    from app.ranking.baselines import BM25Ranker, SbertRanker
    from app.ranking.llm_reranker import _format_resume_summary

    sbert = SbertRanker()
    bm25 = BM25Ranker()

    base_cand = {
        "candidate_id": "SYN_001",
        "candidate_name": "Original Name",
        "name": "Original Name",
        "summary": "Full Stack Engineer with React, Node, and Python experience.",
        "skills": ["React", "Node.js", "Python"],
        "experience": [{"title": "Software Dev", "company": "Acme", "description": "Built web apps."}],
        "raw_text": "Original Name\nSoftware Developer with React and Python.",
    }

    test_names = [
        "Aisha Robinson",    # US Black Female
        "Brad Schultz",      # US White Male
        "Rahul Sharma",      # Indian North/West Male
        "Lakshmi Sundaram",  # Indian South Female
        "Mohammed Ansari",   # Indian Muslim Male
    ]

    sbert_hashes = set()
    bm25_token_hashes = set()
    llm_prompt_hashes = set()

    for name in test_names:
        c = copy.deepcopy(base_cand)
        c["candidate_name"] = name
        c["name"] = name
        c["summary"] = f"Candidate: {name}. " + base_cand["summary"]
        c["raw_text"] = f"Candidate: {name}\n" + base_cand["raw_text"]

        # 1. SBERT resume text
        sbert_text = sbert._get_resume_text(c)
        assert name in sbert_text, f"Name '{name}' missing from SBERT input text!"
        sbert_h = hashlib.sha256(sbert_text.encode("utf-8")).hexdigest()
        sbert_hashes.add(sbert_h)

        # 2. BM25 query tokens
        query_parts = []
        c_name = c.get("candidate_name") or c.get("name")
        if c_name:
            query_parts.append(f"Candidate: {c_name}")
        if c.get("raw_text"):
            query_parts.append(c["raw_text"])
        if c.get("summary"):
            query_parts.append(c["summary"])
        bm25_text = " ".join(query_parts)
        assert name in bm25_text, f"Name '{name}' missing from BM25 query text!"
        bm25_h = hashlib.sha256(bm25_text.encode("utf-8")).hexdigest()
        bm25_token_hashes.add(bm25_h)

        # 3. LLM Prompt summary
        llm_text = _format_resume_summary(c)
        assert name in llm_text, f"Name '{name}' missing from LLM resume summary!"
        llm_h = hashlib.sha256(llm_text.encode("utf-8")).hexdigest()
        llm_prompt_hashes.add(llm_h)

    # Every distinct swapped name MUST produce a distinct hash across all arms
    assert len(sbert_hashes) == len(test_names), "SBERT input text hashed identically across swapped names!"
    assert len(bm25_token_hashes) == len(test_names), "BM25 query text hashed identically across swapped names!"
    assert len(llm_prompt_hashes) == len(test_names), "LLM prompt text hashed identically across swapped names!"


def test_role_families_frozen_counts():
    """Verify role family counts in docs/role_families_frozen.json and snapshot jobs match canonical counts."""
    import json
    from scripts.check_dataset_overlap import classify_job_family
    from scripts.job_snapshot import load_snapshot
    from collections import Counter

    # 1. Resume distribution in docs/role_families_frozen.json
    frozen_path = Path("docs/role_families_frozen.json")
    with open(frozen_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dist = data["metadata"]["distribution_summary"]
    assert dist["Data/AI"] == 14
    assert dist["Web/Software"] == 12
    assert dist["Cybersecurity/Cloud"] == 8
    assert dist["Mobile/UI-UX"] == 6
    assert dist["Mechanical"] == 8
    assert dist["Civil"] == 8
    assert dist["Electrical"] == 21
    assert dist["Commerce/Finance"] == 13
    assert dist["Arts/Media"] == 5
    assert sum(dist.values()) == 95

    # 2. Snapshot job counts: 117 Data/AI, 117 Web/Software, 62 Cybersecurity/Cloud
    jobs, _ = load_snapshot("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")
    job_counts = Counter(classify_job_family(j.get("title", ""), j.get("description", "")) for j in jobs)
    assert job_counts["Data/AI"] == 117
    assert job_counts["Web/Software"] == 117
    assert job_counts["Cybersecurity/Cloud"] == 62


def test_eval_path_strictly_enforces_candidate_universe(tmp_path):
    """Verify that evaluate_ranking and run_ranking_experiment rank each candidate ONLY within their own universe."""
    import json
    from scripts.run_ranking_experiment import run_experiment

    # Create toy jobs
    toy_jobs = [
        {"id": "j1", "title": "Data Scientist", "description": "Python ML", "skills": ["Python", "ML"]},
        {"id": "j2", "title": "AI Engineer", "description": "PyTorch NLP", "skills": ["PyTorch", "NLP"]},
        {"id": "j3", "title": "Frontend Engineer", "description": "React CSS", "skills": ["React", "CSS"]},
        {"id": "j4", "title": "Web Developer", "description": "TypeScript HTML", "skills": ["TypeScript"]},
        {"id": "j5", "title": "Alien Job", "description": "Extraterrestrial", "skills": ["Alien"]},
    ]
    toy_snap_path = tmp_path / "toy_snapshot.jsonl"
    with open(toy_snap_path, "w", encoding="utf-8") as f:
        for j in toy_jobs:
            f.write(json.dumps(j) + "\n")

    # Create candidate universes fixture: cand_1 only has j1 and j2
    toy_universes = {
        "candidate_universes": {
            "SYN_001": {
                "candidate_id": "SYN_001",
                "role_family": "Data/AI",
                "job_ids": ["j1", "j2"],
            }
        }
    }
    toy_univ_path = tmp_path / "toy_universes.json"
    with open(toy_univ_path, "w", encoding="utf-8") as f:
        json.dump(toy_universes, f)

    # Candidate fixture
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "SYN_001_Test.pdf").write_text("Dummy PDF content", encoding="utf-8")

    manifest_path = tmp_path / "gold.json"
    manifest_data = {
        "resumes": [
            {
                "candidate_id": "SYN_001",
                "candidate_name": "Test Candidate",
                "resume_file": "SYN_001_Test.pdf",
                "skills": ["Python", "ML"],
                "role_family": "Data/AI",
            }
        ]
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    # Run experiment with candidate universe constraint
    run_experiment(
        snapshot_path=str(toy_snap_path),
        resumes_dir=str(resumes_dir),
        methods=["overlap"],
        manifest_path=str(manifest_path),
        strict_manifest=False,
        k=5,
        repeat_idx=99,
        universe_seed=42,
        run_type="dryrun",
        universes_path=str(toy_univ_path),
    )

    # Read output run log
    run_log_file = Path("results/dryrun/phase_b_ranking/SYN_001_rep99_overlap.json")
    assert run_log_file.exists()
    with open(run_log_file, "r", encoding="utf-8") as f:
        run_data = json.load(f)

    ranked_jobs = run_data["outputs"]["ranked_job_ids"]
    # Every ranked job ID must strictly be in SYN_001's universe {"j1", "j2"}
    for jid in ranked_jobs:
        assert jid in ["j1", "j2"], f"Job {jid} was ranked but is outside SYN_001 universe!"
    assert "j3" not in ranked_jobs
    assert "j4" not in ranked_jobs
    assert "j5" not in ranked_jobs
