"""Base interfaces and data models for Phase B ranking evaluation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RankingResult:
    """Standardized output structure for all Phase B ranking methods.
    
    Attributes:
        ranked_job_ids: List of job IDs ordered from highest to lowest rank.
        scores: Dict mapping job_id to its raw or composite ranking score.
        method_name: Identifier of the ranking method (e.g. 'bm25', 'sbert', 'overlap', 'hybrid').
        metadata: Detailed execution metadata, parameter weights, latency, candidate count, etc.
    """
    ranked_job_ids: List[str]
    scores: Dict[str, float]
    method_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRanker(ABC):
    """Abstract base class for all ranking methods."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        """Rank a pool of job records for a given anonymized resume.
        
        Args:
            anonymized_resume: Dict containing parsed resume data (skills, summary, experience, etc.)
                               and optionally raw anonymized text.
            job_pool: List of frozen job records from a snapshot.
            k: Top-k items to return in the ranked output.
            
        Returns:
            RankingResult with standardized fields.
        """
        pass
