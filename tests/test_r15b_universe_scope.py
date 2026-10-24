import json
from pathlib import Path
import pytest

from scripts.build_universes import build_universes, load_eval_scope


def test_universe_scope_matches_eval_scope_and_intake():
    """Verify built universes agree with docs/eval_scope.json and results/dryrun/intake_report.json."""
    in_scope_families, deficit_families = load_eval_scope()
    assert in_scope_families == {"Data/AI", "Web/Software", "Cybersecurity/Cloud"}

    intake_path = Path("results/dryrun/intake_report.json")
    assert intake_path.exists(), "intake_report.json must exist"
    with open(intake_path, "r", encoding="utf-8") as f:
        intake_data = json.load(f)

    intake_counts = intake_data["counts"]

    # Inspect candidate_universes.json
    universes_path = Path("results/dryrun/candidate_universes.json")
    assert universes_path.exists(), "candidate_universes.json must exist"
    with open(universes_path, "r", encoding="utf-8") as f:
        u_data = json.load(f)

    u_counts = u_data["counts"]
    u_fams = set(u_data["in_scope_families"])

    # 1. Family agreement
    assert u_fams == in_scope_families, f"Universes families {u_fams} != eval_scope {in_scope_families}"

    # 2. In-scope and out-of-scope count agreement with eval_scope and intake
    assert u_counts["in_scope_candidates"] == 41, f"Expected 41 in-scope, got {u_counts['in_scope_candidates']}"
    assert u_counts["out_of_scope_candidates"] == 54, f"Expected 54 out-of-scope, got {u_counts['out_of_scope_candidates']}"
    assert u_counts["in_scope_candidates"] == intake_counts["in_scope_for_ranking"]
    assert u_counts["out_of_scope_candidates"] == intake_counts["out_of_scope_deficit_families"]

    # 3. In-scope family breakdown
    assert u_counts["in_scope_family_candidates"]["Data/AI"] == 23
    assert u_counts["in_scope_family_candidates"]["Web/Software"] == 10
    assert u_counts["in_scope_family_candidates"]["Cybersecurity/Cloud"] == 8

    # 4. In-scope job pool breakdown
    assert u_counts["in_scope_jobs_count"] == 296
    assert u_counts["in_scope_family_jobs"]["Data/AI"] == 117
    assert u_counts["in_scope_family_jobs"]["Web/Software"] == 117
    assert u_counts["in_scope_family_jobs"]["Cybersecurity/Cloud"] == 62

    # 5. Dev/test split
    assert u_counts["dev_candidates_count"] == 8
    assert u_counts["test_candidates_count"] == 33
