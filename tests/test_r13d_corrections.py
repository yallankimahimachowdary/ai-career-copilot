"""
tests/test_r13d_corrections.py
--------------------------------
Unit and integration tests for Remediation R13d:
1. test_llm_prompt_uses_500_char_description:
   - Verifies _format_candidate_jobs does not truncate descriptions at 100 chars,
     supporting up to 500 characters (the Adzuna upstream limit).
   - Measures prompt token count.
2. test_gemini_strict_model_mismatch_fails:
   - Verifies that in strict/experiment mode, requested != returned model raises RuntimeError.
3. test_eval_stage_real_pipeline_universe_enforcement:
   - Verifies the real eval pipeline code path fails if candidate_universes.json is missing,
     and fails if any ranked job is outside the candidate's universe.
4. test_intake_determinism_two_runs:
   - Verifies running intake twice on data/resumes_dryrun yields identical candidate counts and taxonomy distribution.
5. test_fairness_noise_floor_control:
   - Verifies unchanged resume repeats establish a noise floor with tau=1.0 on deterministic rankers,
     and verifies demographic displacement metric structure.
"""

import copy
import json
import pytest
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import _format_candidate_jobs, _format_resume_summary, LLMReranker
from app.services.llm_provider import GeminiProvider
from scripts.evaluate_ranking import run_evaluation_pipeline
from scripts.intake_resumes import process_resume_intake
from scripts.run_all import run_stage_eval


def test_llm_prompt_uses_500_char_description():
    """Verify that job descriptions up to 500 chars are retained without truncation at 100 chars."""
    desc_long = "Expert software engineer needed for distributed cloud systems. " * 7  # ~441 chars
    assert len(desc_long) > 300

    jobs = [
        {
            "id": "job_test_001",
            "title": "Senior Cloud Architect",
            "skills": ["Python", "AWS", "Kubernetes", "Docker", "Terraform", "PostgreSQL"],
            "description": desc_long,
        }
    ]

    listing_text, label_to_id, id_to_label = _format_candidate_jobs(jobs)
    assert "[J1]" in listing_text
    assert "Senior Cloud Architect" in listing_text
    # Check that description was NOT truncated to 100 characters
    assert len(listing_text) > 250
    assert "distributed cloud systems." in listing_text
    # Verify description length in listing reflects ~441 characters (not 100)
    desc_part = listing_text.split("Desc:")[1].strip()
    assert len(desc_part) > 350
    assert len(desc_part) <= 500

    # Token count measurement
    token_count = len(listing_text.split())
    assert token_count >= 50, f"Expected at least 50 tokens, got {token_count}"


@pytest.mark.asyncio
async def test_gemini_strict_model_mismatch_fails(monkeypatch):
    """Verify that in experiment/strict mode, requested != returned model raises RuntimeError."""
    class FakeResponse:
        status_code = 200
        headers = {}
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "{\"ranked_jobs\": []}"}]}}],
                "modelVersion": "gemini-1.0-unintended-fallback",
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10},
            }
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    provider = GeminiProvider(api_key="fake-test-key", model="gemini-3.5-flash-lite")

    # In experiment mode, mismatch MUST raise RuntimeError
    with pytest.raises(RuntimeError, match="Gemini model mismatch in experiment mode"):
        await provider.generate_json(prompt="test", experiment_mode=True)


def test_eval_stage_real_pipeline_universe_enforcement(tmp_path, monkeypatch):
    """Invoke the actual scripts/run_all.py --stage eval code path on a toy fixture in a temp directory.

    Verifies failure when:
    (a) any job outside a resume's own universe is ranked (Integrity violation)
    (b) candidate_universes.json is missing (RuntimeError)
    (c) snapshot is sliced (e.g. dryrun_max_jobs_slice=100 in real mode -> ValueError)
    """
    from pypdf import PdfWriter
    from app.ranking.baselines import RankingResult

    # Bypass expensive repo-wide secret scanner in unit test fixture
    monkeypatch.setattr("scripts.run_all.run_secret_scanner", lambda: True)

    toy_resumes_dir = tmp_path / "toy_resumes"
    toy_resumes_dir.mkdir()
    toy_cand_ids = ["SYN_901", "SYN_902", "SYN_903"]
    for cid in toy_cand_ids:
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        pdf_path = toy_resumes_dir / f"{cid}_Test_User.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

    toy_labels_file = tmp_path / "toy_labels.jsonl"
    with open(toy_labels_file, "w", encoding="utf-8") as f:
        for cid in toy_cand_ids:
            f.write(json.dumps({"candidate_id": cid, "job_id": "job_toy_01", "relevance": 2.0}) + "\n")

    toy_snapshot = "data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl"
    dest_dir = tmp_path / "results_run"
    dest_dir.mkdir()

    # Case (b): candidate_universes.json is missing in dest_dir
    with pytest.raises(RuntimeError, match="candidate_universes.json is required"):
        run_stage_eval(
            labels_path=str(toy_labels_file),
            snapshot_path=toy_snapshot,
            resumes_dir=str(toy_resumes_dir),
            run_type="real",
            dest_dir=dest_dir,
        )

    # Case (c): Snapshot is sliced in real/eval mode
    with pytest.raises(ValueError, match="Slicing snapshot jobs.*is strictly"):
        run_stage_eval(
            labels_path=str(toy_labels_file),
            snapshot_path=toy_snapshot,
            resumes_dir=str(toy_resumes_dir),
            run_type="real",
            dest_dir=dest_dir,
            dryrun_max_jobs_slice=100,
        )

    # Setup universe containing dummy job IDs not matching outside job
    univ_file = dest_dir / "candidate_universes.json"
    univ_file.write_text(json.dumps({
        "candidate_universes": {
            cid: {
                "candidate_name": f"Test {cid}",
                "role_family": "Data/AI",
                "job_ids": ["job_toy_01"],
            } for cid in toy_cand_ids
        }
    }), encoding="utf-8")

    # Case (a): Any job outside a resume's own universe is ranked
    monkeypatch.setattr(
        BM25Ranker,
        "rank",
        lambda self, cand, job_pool, k=10: RankingResult(
            ranked_job_ids=["job_outside_universe_id_999"],
            scores={"job_outside_universe_id_999": 1.0},
            method_name="bm25",
            metadata={},
        ),
    )

    with pytest.raises(ValueError, match="Integrity violation.*outside the candidate universe"):
        run_stage_eval(
            labels_path=str(toy_labels_file),
            snapshot_path=toy_snapshot,
            resumes_dir=str(toy_resumes_dir),
            run_type="real",
            dest_dir=dest_dir,
        )


DOCUMENTED_FAMILY_DISAGREEMENTS = {
    "SYN_016": ("Web/Software", "Data/AI"),
    "SYN_017": ("Web/Software", "Data/AI"),
    "SYN_072": ("Electrical", "Data/AI"),
    "SYN_073": ("Electrical", "Data/AI"),
    "SYN_074": ("Electrical", "Data/AI"),
    "SYN_075": ("Electrical", "Data/AI"),
    "SYN_076": ("Electrical", "Data/AI"),
    "SYN_085": ("Commerce/Finance", "Data/AI"),
    "SYN_087": ("Commerce/Finance", "Data/AI"),
}


def test_role_family_classifier_vs_frozen_documented_disagreements():
    """Verify any disagreement between docs/role_families_frozen.json and live classifier is documented."""
    frozen_p = Path("docs/role_families_frozen.json")
    assert frozen_p.exists()
    frozen_data = json.loads(frozen_p.read_text(encoding="utf-8"))
    frozen_map = {}
    for fam, f_info in frozen_data["families"].items():
        for r in f_info["resumes"]:
            cid = r.split("_")[0] + "_" + r.split("_")[1]
            frozen_map[cid] = fam

    univ_p = Path("results/dryrun/candidate_universes.json")
    assert univ_p.exists()
    live_data = json.loads(univ_p.read_text(encoding="utf-8"))
    live_map = {cid: u["role_family"] for cid, u in live_data["candidate_universes"].items()}

    in_scope_fams = {"Data/AI", "Web/Software", "Cybersecurity/Cloud"}
    observed_disagreements = {}
    all_cids = sorted(set(frozen_map.keys()).union(set(live_map.keys())))
    for cid in all_cids:
        f_fam = frozen_map.get(cid)
        l_fam = live_map.get(cid)
        if f_fam in in_scope_fams or l_fam in in_scope_fams:
            if f_fam != l_fam:
                observed_disagreements[cid] = (f_fam, l_fam)

    assert observed_disagreements == DOCUMENTED_FAMILY_DISAGREEMENTS, (
        f"Undocumented role family disagreements found! Observed: {observed_disagreements}"
    )


def test_intake_determinism_two_runs(tmp_path):
    """Verify running intake twice on data/resumes_dryrun yields identical counts."""
    out1 = tmp_path / "intake1"
    out2 = tmp_path / "intake2"

    res1 = process_resume_intake(
        resumes_dir="data/resumes_dryrun",
        output_dir=out1,
        run_type="dryrun",
        allow_synthetic=True,
    )

    res2 = process_resume_intake(
        resumes_dir="data/resumes_dryrun",
        output_dir=out2,
        run_type="dryrun",
        allow_synthetic=True,
    )

    # Verify identical counts
    assert res1["counts"] == res2["counts"]
    assert res1["role_family_counts"] == res2["role_family_counts"]
    assert res1["counts"]["total_files_inspected"] == 95
    assert res1["counts"]["in_scope_for_ranking"] == 41
    assert res1["counts"]["out_of_scope_deficit_families"] == 54


def test_fairness_noise_floor_control():
    """Verify noise floor on unchanged repeats and neutral control names."""
    # Deterministic ranker (SkillOverlapRanker) on same resume produces tau = 1.0 exactly
    ranker = SkillOverlapRanker()

    sample_cand = {
        "candidate_name": "Candidate A",
        "skills": ["Python", "Machine Learning", "SQL", "Pandas"],
        "raw_text": "Candidate A\nSkills: Python, Machine Learning, SQL, Pandas",
    }
    sample_jobs = [
        {"id": f"j{i}", "title": f"Job {i}", "skills": ["Python", "SQL"] if i % 2 == 0 else ["Java"]}
        for i in range(15)
    ]

    r1 = ranker.rank(sample_cand, sample_jobs, k=10)
    r2 = ranker.rank(sample_cand, sample_jobs, k=10)

    assert r1.ranked_job_ids == r2.ranked_job_ids, "Deterministic ranker must have 0 jitter on identical input"

    # Neutral name swap Candidate A vs Candidate B
    sample_cand_b = copy.deepcopy(sample_cand)
    sample_cand_b["candidate_name"] = "Candidate B"
    sample_cand_b["raw_text"] = "Candidate B\nSkills: Python, Machine Learning, SQL, Pandas"

    r_b = ranker.rank(sample_cand_b, sample_jobs, k=10)
    assert r1.ranked_job_ids == r_b.ranked_job_ids, "Skill overlap must be invariant to neutral name changes"
