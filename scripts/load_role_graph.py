"""Load role ontology graph into Neo4j from data/graph/role_graph_seed.json.

Idempotent loader that:
1. Creates Role constraint if not exists (name UNIQUE).
2. Merges 52 Role nodes with properties:
   - family, entry_level, experience_years_min, experience_years_max,
   - typical_salary_min, typical_salary_max.
3. Merges (Role)-[:REQUIRES {importance, weight}]->(Skill) edges.
4. Merges (Role)-[:LEADS_TO {typical_years, transition_type}]->(Role) edges.
5. If job_postings exist in PostgreSQL:
   - Maps postings to Role nodes using normalized title matching.
   - Reports counts: mapped, ambiguous, unmapped.
   - Derives support_count on (Role)-[:REQUIRES]->(Skill).
   - Merges (Company)-[:OFFERS {posting_count}]->(Role) edges.
6. Reports total nodes and relationships created/merged.
"""

import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.neo4j import execute_cypher, close_neo4j_driver
from app.db.session import AsyncSessionLocal
from app.models.job_posting import JobPosting
from app.services.matcher_service import FeatureExtractor

SEED_PATH = Path("data/graph/role_graph_seed.json")


def _normalize(text: str) -> str:
    """Normalize text for title comparison."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return " ".join(clean.split())


def _match_posting_to_role(
    title: str,
    role_names: List[str],
) -> Tuple[Optional[str], str]:
    """Map a job posting title to the most specific Role name.
    
    Returns:
        (matched_role_name, status) where status is 'mapped', 'ambiguous', or 'unmapped'.
    """
    norm_title = _normalize(title)
    if not norm_title:
        return None, "unmapped"

    # 1. Exact match
    for r in role_names:
        if norm_title == _normalize(r):
            return r, "mapped"

    # 2. Word boundary substring match
    candidates = []
    for r in role_names:
        norm_r = _normalize(r)
        # Check if role appears as whole word tokens inside title
        pattern = r"\b" + re.escape(norm_r) + r"\b"
        if re.search(pattern, norm_title):
            candidates.append(r)

    if not candidates:
        # Check reverse: if title appears inside role (e.g. "Python Developer" inside "Junior Python Developer")
        for r in role_names:
            norm_r = _normalize(r)
            pattern = r"\b" + re.escape(norm_title) + r"\b"
            if re.search(pattern, norm_r):
                candidates.append(r)

    if not candidates:
        return None, "unmapped"

    if len(candidates) == 1:
        return candidates[0], "mapped"

    # Multiple candidates: sort by length descending (longest / most specific match first)
    candidates.sort(key=lambda x: len(_normalize(x)), reverse=True)
    top_len = len(_normalize(candidates[0]))
    second_len = len(_normalize(candidates[1]))

    if top_len > second_len:
        return candidates[0], "mapped"
    else:
        # Equal length collision -> ambiguous
        return None, "ambiguous"


async def load_role_graph():
    print(f"Reading role seed from {SEED_PATH}...")
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    roles = data.get("roles", [])
    print(f"Found {len(roles)} roles in seed dataset.")

    # 1. Create constraint for Role.name
    try:
        await execute_cypher(
            "CREATE CONSTRAINT role_name_unique IF NOT EXISTS FOR (r:Role) REQUIRE r.name IS UNIQUE"
        )
    except Exception as e:
        print(f"Note on constraint creation: {e}")

    # 2. Batch merge Role nodes
    print("Merging Role nodes into Neo4j...")
    roles_params = [
        {
            "name": r["name"],
            "family": r["family"],
            "level": r.get("level", "mid"),
            "entry_level": bool(r.get("level") == "fresher"),
        }
        for r in roles
    ]

    roles_cypher = """
    UNWIND $roles AS r
    MERGE (role:Role {name: r.name})
    SET role.family = r.family,
        role.level = r.level,
        role.entry_level = r.entry_level,
        role.updated_at = datetime()
    """
    await execute_cypher(roles_cypher, {"roles": roles_params})

    # 3. Batch merge REQUIRES edges
    print("Merging Role -> Skill REQUIRES edges...")
    requires_params = []
    for r in roles:
        for sk in r.get("requires_skills", []):
            imp = sk.get("importance", "core")
            weight = 1.0 if imp == "core" else 0.5
            requires_params.append({
                "role_name": r["name"],
                "skill_name": sk["name"],
                "importance": imp,
                "weight": weight,
            })

    requires_cypher = """
    UNWIND $reqs AS rq
    MATCH (role:Role {name: rq.role_name})
    MERGE (skill:Skill {name: rq.skill_name})
    MERGE (role)-[rel:REQUIRES]->(skill)
    SET rel.importance = rq.importance,
        rel.weight = rq.weight,
        rel.updated_at = datetime()
    """
    await execute_cypher(requires_cypher, {"reqs": requires_params})

    # 4. Batch merge LEADS_TO progression edges
    print("Merging Role -> Role LEADS_TO edges...")
    leads_to_params = []
    for r in roles:
        for edge in r.get("leads_to", []):
            y_min = float(edge.get("typical_years_min", 1.0))
            y_max = float(edge.get("typical_years_max", 2.0))
            typical_years = (y_min + y_max) / 2.0
            leads_to_params.append({
                "source": r["name"],
                "target": edge["target"],
                "typical_years": typical_years,
                "typical_years_min": y_min,
                "typical_years_max": y_max,
                "transition_type": "advancement" if y_max <= 3 else "pivot",
            })

    leads_cypher = """
    UNWIND $edges AS e
    MATCH (r1:Role {name: e.source})
    MATCH (r2:Role {name: e.target})
    MERGE (r1)-[l:LEADS_TO]->(r2)
    SET l.typical_years = e.typical_years,
        l.typical_years_min = e.typical_years_min,
        l.typical_years_max = e.typical_years_max,
        l.transition_type = e.transition_type,
        l.updated_at = datetime()
    """
    await execute_cypher(leads_cypher, {"edges": leads_to_params})

    # 5. Connect to PostgreSQL job_postings to derive support_count and Company-[:OFFERS]->Role
    print("Checking PostgreSQL job_postings for empirical grounding...")
    all_role_names = [r["name"] for r in roles]
    mapped_count = 0
    ambiguous_count = 0
    unmapped_count = 0

    role_skill_counts = defaultdict(int)  # (role, skill) -> count
    company_role_counts = defaultdict(int)  # (company, role) -> count

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                JobPosting.id,
                JobPosting.title,
                JobPosting.company_name,
                JobPosting.skills,
                JobPosting.description,
            )
        )
        postings = result.fetchall()

    print(f"Total job_postings inspected: {len(postings)}")
    for pid, ptitle, comp_name, pskills, pdesc in postings:
        role_match, status = _match_posting_to_role(ptitle, all_role_names)
        if status == "mapped":
            mapped_count += 1
            # Extract skills present in this posting
            raw_skills = pskills if isinstance(pskills, list) else []
            extracted_skills = FeatureExtractor.extract_job_skills(
                description=pdesc or "",
                title=ptitle or "",
                raw_job_skills=raw_skills,
            )
            for sk in extracted_skills:
                role_skill_counts[(role_match, sk)] += 1

            if comp_name and comp_name.strip():
                clean_comp = comp_name.strip()
                company_role_counts[(clean_comp, role_match)] += 1
        elif status == "ambiguous":
            ambiguous_count += 1
        else:
            unmapped_count += 1

    print("\n--- JOB POSTINGS MAPPING SUMMARY ---")
    print(f"  Mapped Postings   : {mapped_count}")
    print(f"  Ambiguous Postings: {ambiguous_count}")
    print(f"  Unmapped Postings : {unmapped_count}")
    print(f"  Mapping Rate      : {mapped_count / max(len(postings), 1) * 100:.1f}%")

    # 6. Apply support_count to Role-REQUIRES->Skill
    if role_skill_counts:
        print(f"\nApplying support_count to {len(role_skill_counts)} Role-REQUIRES->Skill pairs...")
        support_params = [
            {"role": r, "skill": s, "count": cnt}
            for (r, s), cnt in role_skill_counts.items()
        ]
        support_cypher = """
        UNWIND $counts AS sc
        MATCH (role:Role {name: sc.role})-[req:REQUIRES]->(skill:Skill {name: sc.skill})
        SET req.support_count = sc.count
        """
        await execute_cypher(support_cypher, {"counts": support_params})

    # 7. Merge (Company)-[:OFFERS]->(Role)
    if company_role_counts:
        print(f"Merging {len(company_role_counts)} Company -> Role OFFERS edges...")
        offers_params = [
            {"company": comp, "role": role, "count": cnt}
            for (comp, role), cnt in company_role_counts.items()
        ]
        offers_cypher = """
        UNWIND $offers AS o
        MATCH (role:Role {name: o.role})
        MERGE (comp:Company {name: o.company})
        MERGE (comp)-[rel:OFFERS]->(role)
        SET rel.posting_count = o.count,
            rel.updated_at = datetime()
        """
        await execute_cypher(offers_cypher, {"offers": offers_params})

    # 8. Report final Neo4j stats
    stats_nodes = await execute_cypher(
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
    )
    stats_rels = await execute_cypher(
        "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC"
    )

    print("\n--- FINAL NEO4J GRAPH COUNTS ---")
    print("Nodes:")
    for row in stats_nodes:
        print(f"  {row['label']}: {row['count']}")
    print("Relationships:")
    for row in stats_rels:
        print(f"  {row['rel_type']}: {row['count']}")

    await close_neo4j_driver()
    print("\nRole graph loading complete.")


if __name__ == "__main__":
    asyncio.run(load_role_graph())
