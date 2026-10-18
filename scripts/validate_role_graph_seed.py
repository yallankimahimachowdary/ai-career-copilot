"""
scripts/validate_role_graph_seed.py
-----------------------------------
Validates data/graph/role_graph_seed.json against Stage 3 requirements:
  1. Role count is between 40 and 60.
  2. Every role has a valid family (data_ai, web_software, cloud_devops, core_engineering, business_nontech).
  3. Every family has at least one 'fresher' role.
  4. Every non-senior role has at least one outgoing LEADS_TO edge.
  5. No self-loops (role leading to itself).
  6. No orphan roles (every role must have at least one incoming or outgoing edge in the overall graph).
  7. Every required skill exists in the canonical taxonomy (app/core/taxonomy.py).
  8. Every role has between 5 and 12 required skills with importance in ('core', 'nice').
  9. Metadata states source='curated_seed' and notes that LEADS_TO edges are assumptions.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.core.taxonomy import CANONICAL_SKILL_PATTERNS

VALID_FAMILIES = {
    "web_software",
    "data_ai",
    "cloud_devops",
    "core_engineering",
    "business_nontech",
}

VALID_LEVELS = {"fresher", "junior", "mid", "senior"}
VALID_IMPORTANCE = {"core", "nice"}


def validate_seed(path: str = "data/graph/role_graph_seed.json") -> bool:
    if not os.path.exists(path):
        print(f"ERROR: File {path} does not exist.")
        return False

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Metadata check
    metadata = data.get("metadata", {})
    if metadata.get("source") != "curated_seed":
        print("ERROR: Metadata source must be 'curated_seed'")
        return False
    if "assumption" not in metadata.get("note", "").lower():
        print("ERROR: Metadata note must state that LEADS_TO edges are assumptions")
        return False

    roles = data.get("roles", [])
    n_roles = len(roles)
    print(f"Total Roles Found: {n_roles}")
    if not (40 <= n_roles <= 60):
        print(f"ERROR: Role count {n_roles} is not between 40 and 60.")
        return False

    canonical_skills = set(CANONICAL_SKILL_PATTERNS.keys())
    role_names = set()
    role_by_name = {}
    family_counts = {fam: 0 for fam in VALID_FAMILIES}
    freshers_per_family = {fam: 0 for fam in VALID_FAMILIES}

    # Graph edge tracking
    edges = []
    incoming_edges = {r["name"]: 0 for r in roles if "name" in r}
    outgoing_edges = {r["name"]: 0 for r in roles if "name" in r}

    errors = []

    for r in roles:
        name = r.get("name")
        if not name:
            errors.append("Role missing 'name'")
            continue
        if name in role_names:
            errors.append(f"Duplicate role name: '{name}'")
        role_names.add(name)
        role_by_name[name] = r

        fam = r.get("family")
        if fam not in VALID_FAMILIES:
            errors.append(f"Role '{name}' has invalid family '{fam}'")
        else:
            family_counts[fam] += 1

        lvl = r.get("level")
        if lvl not in VALID_LEVELS:
            errors.append(f"Role '{name}' has invalid level '{lvl}'")
        elif lvl == "fresher" and fam in VALID_FAMILIES:
            freshers_per_family[fam] += 1

        # Check skills
        skills = r.get("requires_skills", [])
        if not (5 <= len(skills) <= 12):
            errors.append(f"Role '{name}' has {len(skills)} skills (must be 5 to 12)")

        for s in skills:
            s_name = s.get("name")
            if s_name not in canonical_skills:
                errors.append(f"Role '{name}' requires non-canonical skill: '{s_name}'")
            imp = s.get("importance")
            if imp not in VALID_IMPORTANCE:
                errors.append(f"Role '{name}' skill '{s_name}' has invalid importance '{imp}'")

        # Check outgoing edges
        leads_to = r.get("leads_to", [])
        if lvl != "senior" and len(leads_to) == 0:
            errors.append(f"Non-senior role '{name}' ({lvl}) has 0 outgoing LEADS_TO edges")

        for edge in leads_to:
            target = edge.get("target") if isinstance(edge, dict) else edge
            if target == name:
                errors.append(f"Self-loop detected on role '{name}'")
            edges.append((name, target))
            outgoing_edges[name] += 1
            if target in incoming_edges:
                incoming_edges[target] += 1

    # Check that targets exist
    for src, tgt in edges:
        if tgt not in role_names:
            errors.append(f"Role '{src}' leads to non-existent target role '{tgt}'")

    # Check for orphan roles
    for r_name in role_names:
        if incoming_edges[r_name] == 0 and outgoing_edges[r_name] == 0:
            errors.append(f"Orphan role detected with 0 edges: '{r_name}'")

    # Check fresher roles per family
    for fam, cnt in freshers_per_family.items():
        if cnt == 0:
            errors.append(f"Family '{fam}' has no fresher role")

    # Report results
    print("\n--- ROLE DISTRIBUTION BY FAMILY ---")
    for fam, cnt in family_counts.items():
        print(f"  {fam:<20}: {cnt:2d} roles (freshers: {freshers_per_family[fam]})")

    print(f"\nTotal Directed Progression Edges (LEADS_TO): {len(edges)}")

    if errors:
        print(f"\nVALIDATION FAILED WITH {len(errors)} ERRORS:")
        for e in errors[:20]:
            print(f"  - {e}")
        return False

    print("\nSUCCESS: All role graph seed validation checks passed!")
    return True


if __name__ == "__main__":
    success = validate_seed()
    sys.exit(0 if success else 1)
