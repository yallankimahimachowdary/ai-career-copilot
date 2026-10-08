"""Pydantic schemas for Neo4j Graph Agent queries and metrics."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNodeStats(BaseModel):
    candidates: int = Field(default=0, description="Total Candidate nodes")
    skills: int = Field(default=0, description="Total Skill nodes")
    job_postings: int = Field(default=0, description="Total JobPosting nodes")
    companies: int = Field(default=0, description="Total Company nodes")


class GraphRelStats(BaseModel):
    has_skill: int = Field(default=0, description="Candidate HAS_SKILL relationships")
    requires: int = Field(default=0, description="JobPosting REQUIRES relationships")
    matched_to: int = Field(default=0, description="Candidate MATCHED_TO relationships")
    posted_by: int = Field(default=0, description="JobPosting POSTED_BY relationships")


class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_relationships: int
    nodes: GraphNodeStats
    relationships: GraphRelStats


class SkillBridgeItem(BaseModel):
    skill: str
    from_role_overlap: bool = False
    to_role_overlap: bool = False
    bridge_type: str = Field(description="shared_foundation, stepping_stone, or target_requirement")
    co_occurrence_count: int = Field(default=1, description="Postings mentioning this skill")


class SkillBridgeResponse(BaseModel):
    from_role: str
    to_role: str
    from_postings_found: int
    to_postings_found: int
    shared_foundation_skills: List[str]
    stepping_stone_bridge_skills: List[str]
    target_role_skills: List[str]
    transition_overlap_pct: float
    recommended_learning_order: List[str]
    bridge_summary: str


class CareerPathwaySkillItem(BaseModel):
    skill: str
    co_occurring_with_candidate_skills: int
    unlocks_postings_count: int
    demand_weight: float


class ReachableRoleItem(BaseModel):
    job_id: str
    title: str
    company: Optional[str] = None
    matched_skills: List[str]
    missing_bridge_skills: List[str]
    readiness_pct: float


class CareerPathwayResponse(BaseModel):
    candidate_id: str
    candidate_name: Optional[str] = None
    current_skills_count: int
    current_skills: List[str]
    high_leverage_bridge_skills: List[CareerPathwaySkillItem]
    reachable_roles: List[ReachableRoleItem]
    graph_insight: str


class GraphSyncResponse(BaseModel):
    status: str
    synced_jobs_count: int
    total_skills_count: int
    message: str
