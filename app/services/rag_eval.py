"""
app/services/rag_eval.py
------------------------
Evaluation framework for Retrieval-Augmented Generation (RAG) and Coach Agent advice.

Measures:
  1. Context Recall: proportion of required gold facts present in retrieved contexts.
  2. Context Precision: signal-to-noise ratio in retrieved context chunks.
  3. Answer Factual Consistency / Hallucination Detection: verification of answer
     claims against retrieved source documents, detecting unsupported claims.
  4. Reference-Answer Similarity: token-level precision, recall, and F1 against
     curated gold-standard reference answers.
  5. Source Grounding Verification: checks whether cited sources match retrieved
     source IDs without fabricating evidence.
  6. Human Review Separation: transparently preserves human evaluation status
     without fabricating ratings.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RetrievedChunk(BaseModel):
    source_id: str
    source_type: str
    content: str


class HumanEvaluationRecord(BaseModel):
    status: str = Field(default="pending_review", description="'pending_review', 'reviewed', or 'skipped'")
    rating: Optional[float] = Field(default=None, ge=1.0, le=5.0, description="1-5 Likert scale, None if unreviewed")
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes: Optional[str] = None


class RAGBenchmarkSample(BaseModel):
    sample_id: str
    category: str
    query: str
    retrieved_context: List[RetrievedChunk]
    reference_answer: str
    required_key_facts: List[str]
    prohibited_hallucinations: List[str] = Field(default_factory=list)
    human_evaluation: HumanEvaluationRecord = Field(default_factory=HumanEvaluationRecord)


class RAGSampleEvaluationResult(BaseModel):
    sample_id: str
    category: str
    context_recall: float = Field(..., ge=0.0, le=1.0)
    context_precision: float = Field(..., ge=0.0, le=1.0)
    answer_factual_consistency: float = Field(..., ge=0.0, le=1.0)
    reference_similarity_f1: float = Field(..., ge=0.0, le=1.0)
    hallucinations_detected: List[str] = Field(default_factory=list)
    missing_key_facts: List[str] = Field(default_factory=list)
    sources_cited: List[str] = Field(default_factory=list)
    valid_source_grounding: bool
    human_evaluation_status: str
    human_rating: Optional[float] = None


class RAGSuiteEvaluationReport(BaseModel):
    timestamp: str
    dataset_path: str
    dataset_sha256: str
    total_samples: int
    mean_context_recall: float
    mean_context_precision: float
    mean_factual_consistency: float
    mean_reference_similarity_f1: float
    hallucination_rate: float
    grounding_pass_rate: float
    automated_eval_provenance: str
    human_review_summary: Dict[str, Any]
    sample_results: List[RAGSampleEvaluationResult]


# ---------------------------------------------------------------------------
# Evaluation Metrics Helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, remove thousands-commas, and collapse whitespace."""
    text = text.lower()
    text = re.sub(r"(?<=\d),(?=\d)", "", text)  # Remove commas in numbers like 160,000 -> 160000
    text = re.sub(r"[,\'\"]", "", text)
    text = re.sub(r"[^\w\s\$\%\-\.]", " ", text)
    return " ".join(text.split())


def _tokenize(text: str) -> List[str]:
    """Tokenize normalized string into words."""
    norm = _normalize_text(text)
    return [t for t in norm.split() if t]


def _fact_matches(fact: str, text_norm: str) -> bool:
    """Checks whether a key fact appears in normalized text, allowing inflection stems."""
    fact_norm = _normalize_text(fact)
    if fact_norm in text_norm:
        return True
    tokens = fact_norm.split()
    text_tokens = text_norm.split()
    for tok in tokens:
        stem = tok[:5] if len(tok) >= 5 else tok
        if not any(tt.startswith(stem) or stem in tt for tt in text_tokens):
            return False
    return True


def compute_token_f1(prediction: str, reference: str) -> float:
    """
    Computes token-level F1 overlap score between prediction and reference answer.
    """
    pred_tokens = _tokenize(prediction)
    ref_tokens = _tokenize(reference)

    if not pred_tokens or not ref_tokens:
        return 0.0

    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_same = sum(common.values())

    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return round(f1, 4)


def compute_context_recall(
    required_facts: List[str],
    retrieved_contexts: List[str],
) -> Tuple[float, List[str]]:
    """
    Measures what fraction of required key facts are present in retrieved contexts.
    Returns (recall_score, list_of_missing_facts).
    """
    if not required_facts:
        return 1.0, []

    combined_context = _normalize_text(" ".join(retrieved_contexts))
    missing: List[str] = []

    for fact in required_facts:
        if not _fact_matches(fact, combined_context):
            missing.append(fact)

    recall = (len(required_facts) - len(missing)) / len(required_facts)
    return round(recall, 4), missing


def compute_context_precision(
    required_facts: List[str],
    retrieved_contexts: List[str],
) -> float:
    """
    Measures the signal-to-noise ratio in retrieved context chunks.
    A context chunk is considered relevant if it contains at least one required key fact.
    """
    if not retrieved_contexts:
        return 0.0

    relevant_chunks = 0
    for chunk in retrieved_contexts:
        chunk_norm = _normalize_text(chunk)
        if any(_fact_matches(fact, chunk_norm) for fact in required_facts):
            relevant_chunks += 1

    precision = relevant_chunks / len(retrieved_contexts)
    return round(precision, 4)


def check_factual_consistency(
    generated_answer: str,
    retrieved_contexts: List[str],
    required_facts: List[str],
    prohibited_hallucinations: List[str],
) -> Tuple[float, List[str], List[str]]:
    """
    Evaluates factual consistency and detects hallucinations.
    
    Returns:
      (consistency_score, missing_key_facts, detected_hallucinations)
    """
    ans_norm = _normalize_text(generated_answer)
    combined_ctx_norm = _normalize_text(" ".join(retrieved_contexts))

    # 1. Detect explicit prohibited hallucinations
    detected_hallucinations: List[str] = []
    for hallucination in prohibited_hallucinations:
        h_norm = _normalize_text(hallucination)
        if h_norm in ans_norm and h_norm not in combined_ctx_norm:
            detected_hallucinations.append(hallucination)

    # 2. Check presence of required key facts in generated answer
    missing_facts: List[str] = []
    for fact in required_facts:
        if not _fact_matches(fact, ans_norm):
            missing_facts.append(fact)

    # Base factual support score from key facts
    if required_facts:
        fact_coverage = (len(required_facts) - len(missing_facts)) / len(required_facts)
    else:
        fact_coverage = 1.0

    # Penalize detected hallucinations heavily
    penalty = 0.5 * len(detected_hallucinations)
    consistency_score = max(0.0, min(1.0, round(fact_coverage - penalty, 4)))

    return consistency_score, missing_facts, detected_hallucinations


def verify_source_grounding(
    citations: List[str],
    retrieved_chunks: List[RetrievedChunk],
) -> bool:
    """
    Verifies that all citations match actual retrieved context source IDs.
    """
    if not citations:
        # If no citations provided, grounding is trivially valid if context is unreferenced
        return True

    valid_source_ids = {c.source_id for c in retrieved_chunks}
    for citation in citations:
        if citation not in valid_source_ids:
            return False
    return True


# ---------------------------------------------------------------------------
# Evaluator Service
# ---------------------------------------------------------------------------

class RAGCoachEvaluator:
    """
    Reproducible RAG and Coach answer evaluation runner.
    """

    def evaluate_sample(
        self,
        sample: RAGBenchmarkSample,
        generated_answer: str,
        citations: Optional[List[str]] = None,
    ) -> RAGSampleEvaluationResult:
        """
        Evaluates a single RAG generation against the benchmark sample.
        """
        contexts = [c.content for c in sample.retrieved_context]
        citations = citations or []

        # 1. Context metrics
        ctx_recall, missing_from_ctx = compute_context_recall(sample.required_key_facts, contexts)
        ctx_precision = compute_context_precision(sample.required_key_facts, contexts)

        # 2. Answer Grounding and Hallucination metrics
        consistency, missing_facts, hallucinations = check_factual_consistency(
            generated_answer=generated_answer,
            retrieved_contexts=contexts,
            required_facts=sample.required_key_facts,
            prohibited_hallucinations=sample.prohibited_hallucinations,
        )

        # 3. Reference-Answer Similarity
        ref_f1 = compute_token_f1(generated_answer, sample.reference_answer)

        # 4. Source grounding verification
        valid_grounding = verify_source_grounding(citations, sample.retrieved_context)

        return RAGSampleEvaluationResult(
            sample_id=sample.sample_id,
            category=sample.category,
            context_recall=ctx_recall,
            context_precision=ctx_precision,
            answer_factual_consistency=consistency,
            reference_similarity_f1=ref_f1,
            hallucinations_detected=hallucinations,
            missing_key_facts=missing_facts,
            sources_cited=citations,
            valid_source_grounding=valid_grounding,
            human_evaluation_status=sample.human_evaluation.status,
            human_rating=sample.human_evaluation.rating,
        )

    def evaluate_benchmark_suite(
        self,
        dataset_path: Path,
        answer_generator: Optional[Callable[[RAGBenchmarkSample], Tuple[str, List[str]]]] = None,
    ) -> RAGSuiteEvaluationReport:
        """
        Runs evaluation across the complete benchmark dataset.
        If answer_generator is None, evaluates the reference answers as self-consistency benchmark.
        """
        if not dataset_path.exists():
            raise FileNotFoundError(f"Benchmark dataset not found at {dataset_path}")

        raw_bytes = dataset_path.read_bytes()
        dataset_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        raw_data = json.loads(raw_bytes.decode("utf-8"))

        samples = [RAGBenchmarkSample.model_validate(s) for s in raw_data.get("samples", [])]
        if not samples:
            raise ValueError("No samples found in benchmark dataset.")

        results: List[RAGSampleEvaluationResult] = []

        for sample in samples:
            if answer_generator is not None:
                gen_answer, citations = answer_generator(sample)
            else:
                # Default baseline: evaluate reference answer with its source IDs
                gen_answer = sample.reference_answer
                citations = [c.source_id for c in sample.retrieved_context]

            res = self.evaluate_sample(sample, gen_answer, citations)
            results.append(res)

        total = len(results)
        mean_recall = round(sum(r.context_recall for r in results) / total, 4)
        mean_precision = round(sum(r.context_precision for r in results) / total, 4)
        mean_consistency = round(sum(r.answer_factual_consistency for r in results) / total, 4)
        mean_f1 = round(sum(r.reference_similarity_f1 for r in results) / total, 4)
        hallucinated_count = sum(1 for r in results if r.hallucinations_detected)
        hallucination_rate = round(hallucinated_count / total, 4)
        grounded_count = sum(1 for r in results if r.valid_source_grounding and r.answer_factual_consistency >= 0.8)
        grounding_pass_rate = round(grounded_count / total, 4)

        human_review_summary = {
            "pending_review_count": sum(1 for r in results if r.human_evaluation_status == "pending_review"),
            "reviewed_count": sum(1 for r in results if r.human_evaluation_status == "reviewed"),
            "unreviewed_rating_fabricated": False,
        }

        return RAGSuiteEvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            dataset_path=str(dataset_path),
            dataset_sha256=dataset_sha256,
            total_samples=total,
            mean_context_recall=mean_recall,
            mean_context_precision=mean_precision,
            mean_factual_consistency=mean_consistency,
            mean_reference_similarity_f1=mean_f1,
            hallucination_rate=hallucination_rate,
            grounding_pass_rate=grounding_pass_rate,
            automated_eval_provenance="deterministic_algorithmic_grounding_evaluator_v1",
            human_review_summary=human_review_summary,
            sample_results=results,
        )


rag_coach_evaluator = RAGCoachEvaluator()
