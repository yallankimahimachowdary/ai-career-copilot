"""Graph Service — Neo4j integration for Candidate, Skill, and JobPosting knowledge graph."""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.neo4j import execute_cypher
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.graph import (
    CareerPathwayResponse,
    CareerPathwaySkillItem,
    GraphNodeStats,
    GraphRelStats,
    GraphStatsResponse,
    ReachableRoleItem,
    SkillBridgeItem,
    SkillBridgeResponse,
)
from app.services.matcher_service import FeatureExtractor


# Known category codes to exclude from skill nodes
KNOWN_CATEGORY_CODES = {
    "ART", "DSGN", "ADVR", "PRDM", "DIST", "EDU", "TRNG", "PRJM",
    "CNSL", "PRCH", "SUPL", "ANLS", "HCPR", "RSCH", "SCI", "GENB",
    "CUST", "STRA", "FIN", "OTHR", "LGL", "ENG", "QA", "BD",
    "IT", "ADM", "PROD", "MRKT", "PR", "WRT", "ACCT", "HR",
    "MNFC", "SALE", "MGMT",
}


def _clean_skills(skills: List[str]) -> List[str]:
    """Sanitize and deduplicate skill tokens for graph node creation."""
    cleaned: List[str] = []
    seen: Set[str] = set()
    for s in skills:
        if not s or not isinstance(s, str):
            continue
        token = s.strip()
        if not token or len(token) > 50:
            continue
        if token.upper() in KNOWN_CATEGORY_CODES:
            continue
        lower_token = token.lower()
        if lower_token not in seen:
            seen.add(lower_token)
            cleaned.append(token)
    return cleaned


class GraphService:
    """Orchestrates Neo4j graph operations across Parser and Matcher agents."""

    # -----------------------------------------------------------------------
    # Node & Relationship Mutation APIs
    # -----------------------------------------------------------------------

    async def sync_candidate(
        self,
        candidate_id: str,
        name: Optional[str],
        email: Optional[str],
        skills: List[str],
    ) -> Dict[str, Any]:
        """Upsert a Candidate node and link to Skill nodes via HAS_SKILL relationships."""
        cleaned_skills = _clean_skills(skills)
        query = """
        MERGE (c:Candidate {id: $candidate_id})
        SET c.name = $name,
            c.email = $email,
            c.updated_at = datetime()
        WITH c
        UNWIND $skills AS skill_name
        MERGE (s:Skill {name: skill_name})
        MERGE (c)-[r:HAS_SKILL]->(s)
        SET r.updated_at = datetime()
        RETURN c.id AS candidate_id, count(s) AS skills_linked
        """
        params = {
            "candidate_id": str(candidate_id),
            "name": name or "Anonymous Candidate",
            "email": email or "",
            "skills": cleaned_skills,
        }
        res = await execute_cypher(query, params)
        logger.info(f"Graph: Synced candidate {candidate_id} with {len(cleaned_skills)} skills.")
        return res[0] if res else {"candidate_id": candidate_id, "skills_linked": len(cleaned_skills)}

    async def sync_job_posting(
        self,
        job_id: str,
        title: str,
        company_name: Optional[str] = None,
        location: Optional[str] = None,
        work_type: Optional[str] = None,
        salary: Optional[float] = None,
        skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Upsert a JobPosting node, optional Company node, and REQUIRES Skill relationships."""
        cleaned_skills = _clean_skills(skills or [])
        query = """
        MERGE (j:JobPosting {id: $job_id})
        SET j.title = $title,
            j.location = $location,
            j.work_type = $work_type,
            j.salary = $salary,
            j.company_name = $company_name,
            j.updated_at = datetime()
        WITH j
        FOREACH (_ IN CASE WHEN $company_name IS NOT NULL AND $company_name <> '' THEN [1] ELSE [] END |
            MERGE (comp:Company {name: $company_name})
            MERGE (j)-[:POSTED_BY]->(comp)
        )
        WITH j
        UNWIND $skills AS skill_name
        MERGE (s:Skill {name: skill_name})
        MERGE (j)-[r:REQUIRES]->(s)
        SET r.updated_at = datetime()
        RETURN j.id AS job_id, count(s) AS skills_linked
        """
        params = {
            "job_id": str(job_id),
            "title": title or "Untitled Role",
            "company_name": company_name or "",
            "location": location or "",
            "work_type": work_type or "",
            "salary": float(salary) if salary is not None else None,
            "skills": cleaned_skills,
        }
        res = await execute_cypher(query, params)
        return res[0] if res else {"job_id": job_id, "skills_linked": len(cleaned_skills)}

    async def record_match(
        self,
        candidate_id: str,
        job_id: str,
        score: float,
        composite_score: Optional[float] = None,
        xgboost_score: Optional[float] = None,
        rank: Optional[int] = None,
    ) -> None:
        """Create or update a MATCHED_TO relationship between Candidate and JobPosting."""
        query = """
        MATCH (c:Candidate {id: $candidate_id})
        MATCH (j:JobPosting {id: $job_id})
        MERGE (c)-[r:MATCHED_TO]->(j)
        SET r.score = $score,
            r.composite_score = $composite_score,
            r.xgboost_score = $xgboost_score,
            r.rank = $rank,
            r.matched_at = datetime()
        """
        params = {
            "candidate_id": str(candidate_id),
            "job_id": str(job_id),
            "score": float(score),
            "composite_score": float(composite_score) if composite_score is not None else None,
            "xgboost_score": float(xgboost_score) if xgboost_score is not None else None,
            "rank": int(rank) if rank is not None else None,
        }
        await execute_cypher(query, params)

    async def record_matches_for_resume(
        self,
        resume_id: str,
        matches: List[Any],
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Batch-sync matched jobs and their skills to Neo4j, then create MATCHED_TO edges."""
        if not matches:
            return

        # 1. Ensure Candidate exists
        check_cand = await execute_cypher(
            "MATCH (c:Candidate {id: $id}) RETURN count(c) AS cnt",
            {"id": str(resume_id)},
        )
        if not check_cand or check_cand[0]["cnt"] == 0:
            if db:
                r_stmt = select(Resume).where(Resume.id == resume_id)
                r_res = await db.execute(r_stmt)
                resume = r_res.scalar_one_or_none()
                if resume:
                    parsed = resume.parsed_data or {}
                    skills = parsed.get("skills", [])
                    await self.sync_candidate(
                        candidate_id=resume.id,
                        name=resume.candidate_name,
                        email=resume.email,
                        skills=skills,
                    )

        # 2. Sync each matched job and record MATCHED_TO relationship
        for item in matches:
            job_id = getattr(item, "job_id", None)
            if not job_id:
                continue

            # Collect all relevant skills from the match breakdown or job
            skills_breakdown = getattr(item, "skills_breakdown", None)
            skills: List[str] = []
            if skills_breakdown:
                skills.extend(getattr(skills_breakdown, "matched_skills", []))
                skills.extend(getattr(skills_breakdown, "missing_must_have", []))
                skills.extend(getattr(skills_breakdown, "missing_nice_to_have", []))

            await self.sync_job_posting(
                job_id=str(job_id),
                title=getattr(item, "title", "Role"),
                company_name=getattr(item, "company_name", None),
                location=getattr(item, "location", None),
                work_type=getattr(item, "work_type", None),
                skills=skills,
            )

            await self.record_match(
                candidate_id=str(resume_id),
                job_id=str(job_id),
                score=getattr(item, "final_score", 0.0),
                composite_score=getattr(item, "composite_score", None),
                xgboost_score=getattr(item, "xgboost_score", None),
                rank=getattr(item, "rank", None),
            )

        logger.info(f"Graph: Recorded {len(matches)} MATCHED_TO relationships for resume {resume_id}.")

    async def record_job_candidate_matches(
        self,
        job: JobPosting,
        candidates: List[Any],
    ) -> None:
        """Batch-sync matched candidates for a specific job posting."""
        if not candidates:
            return

        raw_skills = job.skills if isinstance(job.skills, list) else []
        extracted_skills = FeatureExtractor.extract_job_skills(
            description=job.description or "",
            title=job.title or "",
            raw_job_skills=raw_skills,
        )
        await self.sync_job_posting(
            job_id=str(job.id),
            title=job.title or "",
            company_name=job.company_name,
            location=job.location,
            work_type=job.work_type,
            skills=extracted_skills,
        )

        for c_item in candidates:
            cand_id = getattr(c_item, "resume_id", None)
            if not cand_id:
                continue
            await self.record_match(
                candidate_id=str(cand_id),
                job_id=str(job.id),
                score=getattr(c_item, "final_score", 0.0),
                composite_score=getattr(c_item, "composite_score", None),
                xgboost_score=getattr(c_item, "xgboost_score", None),
                rank=getattr(c_item, "rank", None),
            )

    # -----------------------------------------------------------------------
    # Graph Read / Analytical Queries (Postgres can't easily do)
    # -----------------------------------------------------------------------

    async def get_graph_stats(self) -> GraphStatsResponse:
        """Aggregate total node counts and relationship counts across the graph."""
        nodes_q = """
        RETURN
          count { MATCH (c:Candidate) } AS candidates,
          count { MATCH (s:Skill) } AS skills,
          count { MATCH (j:JobPosting) } AS job_postings,
          count { MATCH (comp:Company) } AS companies
        """
        rels_q = """
        RETURN
          count { MATCH ()-[r:HAS_SKILL]->() } AS has_skill,
          count { MATCH ()-[r:REQUIRES]->() } AS requires,
          count { MATCH ()-[r:MATCHED_TO]->() } AS matched_to,
          count { MATCH ()-[r:POSTED_BY]->() } AS posted_by
        """
        node_res = await execute_cypher(nodes_q)
        rel_res = await execute_cypher(rels_q)

        n_row = node_res[0] if node_res else {"candidates": 0, "skills": 0, "job_postings": 0, "companies": 0}
        r_row = rel_res[0] if rel_res else {"has_skill": 0, "requires": 0, "matched_to": 0, "posted_by": 0}

        nodes = GraphNodeStats(
            candidates=n_row.get("candidates", 0),
            skills=n_row.get("skills", 0),
            job_postings=n_row.get("job_postings", 0),
            companies=n_row.get("companies", 0),
        )
        rels = GraphRelStats(
            has_skill=r_row.get("has_skill", 0),
            requires=r_row.get("requires", 0),
            matched_to=r_row.get("matched_to", 0),
            posted_by=r_row.get("posted_by", 0),
        )

        total_nodes = nodes.candidates + nodes.skills + nodes.job_postings + nodes.companies
        total_rels = rels.has_skill + rels.requires + rels.matched_to + rels.posted_by

        return GraphStatsResponse(
            total_nodes=total_nodes,
            total_relationships=total_rels,
            nodes=nodes,
            relationships=rels,
        )

    async def find_bridge_skills(self, from_role: str, to_role: str) -> SkillBridgeResponse:
        """Discover skills that bridge two distinct roles via graph topology.

        Traverses the graph to uncover:
        1. Shared foundation skills common to both role distributions.
        2. Stepping-stone bridge skills that co-occur in hybrid postings bridging both.
        3. Target requirements needed to complete the career transition.
        """
        query = """
        MATCH (fromJ:JobPosting)
        WHERE toLower(fromJ.title) CONTAINS toLower($from_role)
        MATCH (fromJ)-[:REQUIRES]->(sFrom:Skill)
        WITH collect(DISTINCT sFrom.name) AS fromSkills, count(DISTINCT fromJ) AS fromCount

        MATCH (toJ:JobPosting)
        WHERE toLower(toJ.title) CONTAINS toLower($to_role)
        MATCH (toJ)-[:REQUIRES]->(sTo:Skill)
        WITH fromSkills, fromCount, collect(DISTINCT sTo.name) AS toSkills, count(DISTINCT toJ) AS toCount

        RETURN fromSkills, fromCount, toSkills, toCount
        """
        res = await execute_cypher(query, {"from_role": from_role, "to_role": to_role})

        if not res or (res[0]["fromCount"] == 0 and res[0]["toCount"] == 0):
            return SkillBridgeResponse(
                from_role=from_role,
                to_role=to_role,
                from_postings_found=0,
                to_postings_found=0,
                shared_foundation_skills=[],
                stepping_stone_bridge_skills=[],
                target_role_skills=[],
                transition_overlap_pct=0.0,
                recommended_learning_order=[],
                bridge_summary=f"No graph postings found matching '{from_role}' or '{to_role}'. Try synchronizing job postings to Neo4j first.",
            )

        row = res[0]
        from_skills_set = set(row.get("fromSkills") or [])
        to_skills_set = set(row.get("toSkills") or [])
        from_count = row.get("fromCount", 0)
        to_count = row.get("toCount", 0)

        shared = sorted(list(from_skills_set.intersection(to_skills_set)))
        target_gaps = sorted(list(to_skills_set.difference(from_skills_set)))

        # Find graph stepping stones: skills that co-occur with both from_skills and to_skills in intermediate postings
        stepping_stone_query = """
        MATCH (midJ:JobPosting)-[:REQUIRES]->(sMid:Skill)
        WHERE NOT sMid.name IN $shared_and_target
        MATCH (midJ)-[:REQUIRES]->(s1:Skill) WHERE s1.name IN $from_skills
        MATCH (midJ)-[:REQUIRES]->(s2:Skill) WHERE s2.name IN $to_skills
        RETURN sMid.name AS skill, count(DISTINCT midJ) AS co_occurs
        ORDER BY co_occurs DESC
        LIMIT 6
        """
        shared_and_target = list(from_skills_set.union(to_skills_set))
        stepping_res = await execute_cypher(
            stepping_stone_query,
            {
                "shared_and_target": shared_and_target,
                "from_skills": list(from_skills_set),
                "to_skills": list(to_skills_set),
            },
        )
        stepping_stones = [r["skill"] for r in stepping_res if r.get("skill")]

        total_unique = len(from_skills_set.union(to_skills_set))
        overlap_pct = round((len(shared) / max(total_unique, 1)) * 100, 1)

        # Recommended learning order: stepping stones first (easier transition), then core target gaps
        learning_order = stepping_stones[:3] + target_gaps[:5]

        summary = (
            f"Transitioning from '{from_role}' to '{to_role}' has a {overlap_pct}% foundational skill overlap "
            f"across {from_count + to_count} analyzed postings. "
            f"{len(shared)} shared skills provide a solid base ({', '.join(shared[:4]) if shared else 'none'}). "
            f"Targeting bridge skills like {', '.join(learning_order[:3]) if learning_order else 'specialized tools'} "
            f"offers the most efficient transition path."
        )

        return SkillBridgeResponse(
            from_role=from_role,
            to_role=to_role,
            from_postings_found=from_count,
            to_postings_found=to_count,
            shared_foundation_skills=shared,
            stepping_stone_bridge_skills=stepping_stones,
            target_role_skills=target_gaps,
            transition_overlap_pct=overlap_pct,
            recommended_learning_order=learning_order,
            bridge_summary=summary,
        )

    async def find_candidate_career_pathway(self, candidate_id: str) -> CareerPathwayResponse:
        """Compute high-leverage skill recommendations using 2-hop collaborative graph traversal.

        Identifies skills that co-occur most strongly with the candidate's existing skill set in
        industry postings, and computes which reachable roles become unlocked.
        """
        cand_q = """
        MATCH (c:Candidate {id: $candidate_id})
        OPTIONAL MATCH (c)-[:HAS_SKILL]->(s:Skill)
        RETURN c.name AS name, collect(s.name) AS skills
        """
        cand_res = await execute_cypher(cand_q, {"candidate_id": str(candidate_id)})
        if not cand_res or not cand_res[0].get("name"):
            return CareerPathwayResponse(
                candidate_id=candidate_id,
                candidate_name=None,
                current_skills_count=0,
                current_skills=[],
                high_leverage_bridge_skills=[],
                reachable_roles=[],
                graph_insight="Candidate node not found in Neo4j. Upload or parse a resume to initialize the candidate graph.",
            )

        cand_name = cand_res[0]["name"]
        curr_skills = cand_res[0]["skills"] or []

        # 2-Hop graph query:
        # (Candidate)-[:HAS_SKILL]->(Skill)<-[:REQUIRES]-(JobPosting)-[:REQUIRES]->(BridgeSkill)
        pathway_q = """
        MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(candSkill:Skill)
        MATCH (candSkill)<-[:REQUIRES]-(j:JobPosting)-[:REQUIRES]->(bridgeSkill:Skill)
        WHERE NOT (c)-[:HAS_SKILL]->(bridgeSkill)
        WITH bridgeSkill, count(DISTINCT candSkill) AS matched_co_occurs, count(DISTINCT j) AS unlocks_jobs
        RETURN bridgeSkill.name AS skill, matched_co_occurs, unlocks_jobs,
               round(toFloat(unlocks_jobs) * (1.0 + toFloat(matched_co_occurs) / 10.0), 2) AS demand_weight
        ORDER BY demand_weight DESC, unlocks_jobs DESC
        LIMIT 8
        """
        pathway_res = await execute_cypher(pathway_q, {"candidate_id": str(candidate_id)})
        high_leverage_skills = [
            CareerPathwaySkillItem(
                skill=r["skill"],
                co_occurring_with_candidate_skills=r["matched_co_occurs"],
                unlocks_postings_count=r["unlocks_jobs"],
                demand_weight=r["demand_weight"],
            )
            for r in pathway_res
        ]

        # Reachable roles query: finds postings where candidate has >30% matching skills
        roles_q = """
        MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(s:Skill)
        MATCH (j:JobPosting)-[:REQUIRES]->(reqSkill:Skill)
        WITH c, j, collect(DISTINCT reqSkill.name) AS all_reqs,
             collect(DISTINCT CASE WHEN (c)-[:HAS_SKILL]->(reqSkill) THEN reqSkill.name END) AS matched_raw
        WITH j, all_reqs, [x IN matched_raw WHERE x IS NOT NULL] AS matched
        WHERE size(all_reqs) > 0 AND size(matched) > 0
        WITH j, all_reqs, matched,
             [sk IN all_reqs WHERE NOT sk IN matched] AS missing,
             round((toFloat(size(matched)) / toFloat(size(all_reqs))) * 100, 1) AS readiness
        WHERE readiness >= 25.0
        RETURN j.id AS job_id, j.title AS title, j.company_name AS company,
               matched, missing, readiness
        ORDER BY readiness DESC, size(all_reqs) DESC
        LIMIT 6
        """
        roles_res = await execute_cypher(roles_q, {"candidate_id": str(candidate_id)})
        reachable_roles = [
            ReachableRoleItem(
                job_id=r["job_id"],
                title=r["title"],
                company=r.get("company"),
                matched_skills=r["matched"],
                missing_bridge_skills=r["missing"][:5],
                readiness_pct=r["readiness"],
            )
            for r in roles_res
        ]

        insight = (
            f"Based on {len(curr_skills)} skills in your graph profile, Neo4j identified "
            f"{len(high_leverage_skills)} high-velocity bridge skills. "
            f"Acquiring {', '.join(s.skill for s in high_leverage_skills[:3]) if high_leverage_skills else 'adjacent cloud skills'} "
            f"unlocks the highest concentration of industry postings."
        )

        return CareerPathwayResponse(
            candidate_id=candidate_id,
            candidate_name=cand_name,
            current_skills_count=len(curr_skills),
            current_skills=curr_skills,
            high_leverage_bridge_skills=high_leverage_skills,
            reachable_roles=reachable_roles,
            graph_insight=insight,
        )

    async def sync_all_existing_jobs(self, db: AsyncSession) -> int:
        """Batch-sync all PostgreSQL JobPostings into Neo4j."""
        stmt = select(JobPosting)
        res = await db.execute(stmt)
        postings = res.scalars().all()

        synced = 0
        for p in postings:
            raw_skills = p.skills if isinstance(p.skills, list) else []
            extracted_skills = FeatureExtractor.extract_job_skills(
                description=p.description or "",
                title=p.title or "",
                raw_job_skills=raw_skills,
            )
            salary_val = p.med_salary or p.min_salary
            await self.sync_job_posting(
                job_id=str(p.id),
                title=p.title or "",
                company_name=p.company_name,
                location=p.location,
                work_type=p.work_type,
                salary=salary_val,
                skills=extracted_skills,
            )
            synced += 1

        logger.info(f"Graph: Successfully synchronized {synced} job postings from PostgreSQL to Neo4j.")
        return synced


# Module-level singleton
graph_service = GraphService()
