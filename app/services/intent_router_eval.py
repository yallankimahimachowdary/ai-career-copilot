"""
app/services/intent_router_eval.py
----------------------------------
Evaluation module for Query Intent Router.
Computes accuracy, macro-F1, per-intent precision/recall/F1, and confusion matrix
over versioned ground-truth benchmark datasets without fabricating results.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.schemas.chat import IntentType
from app.services.router_service import router_service


CANONICAL_INTENT_MAP = {
    # 5 target intents
    "job_search": "job_search",
    "skill_gap_analysis": "skill_gap_analysis",
    "resume_feedback": "resume_feedback",
    "career_advice": "career_advice",
    "interview_preparation": "interview_preparation",

    # Enum string values
    IntentType.JOB_SEARCH.value: "job_search",
    IntentType.JOB_SEARCH_AND_MATCH.value: "job_search",
    IntentType.SKILL_GAP_ANALYSIS.value: "skill_gap_analysis",
    IntentType.SKILL_PROGRESSION_AND_PATH.value: "skill_gap_analysis",
    IntentType.RESUME_FEEDBACK.value: "resume_feedback",
    IntentType.CAREER_ADVICE.value: "career_advice",
    IntentType.MACRO_MARKET_DYNAMICS.value: "career_advice",
    IntentType.INTERVIEW_PREPARATION.value: "interview_preparation",
    IntentType.INTERVIEW_COACHING.value: "interview_preparation",
}


def to_canonical_intent(raw_intent: Any) -> str:
    """Normalize any intent representation (Enum, str, or legacy name) to canonical intent string."""
    if hasattr(raw_intent, "value"):
        key = raw_intent.value
    else:
        key = str(raw_intent).strip()
    return CANONICAL_INTENT_MAP.get(key, key.lower().replace("-", "_").replace(" ", "_"))


async def evaluate_intent_benchmark(
    benchmark_path: str = "data/evaluation/query_intent_benchmark_v1.json",
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates the intent router on a benchmark dataset.
    Returns honest accuracy, macro-F1, and per-intent metrics.
    """
    path = Path(benchmark_path)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")

    raw_bytes = path.read_bytes()
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
    data = json.loads(raw_bytes.decode("utf-8"))

    samples: List[Dict[str, Any]] = data.get("samples", [])
    if not samples:
        raise ValueError(f"No samples found in benchmark dataset: {benchmark_path}")

    metadata = data.get("metadata", {})
    all_intents = [
        "job_search",
        "skill_gap_analysis",
        "resume_feedback",
        "career_advice",
        "interview_preparation",
    ]

    y_true: List[str] = []
    y_pred: List[str] = []
    per_sample_results: List[Dict[str, Any]] = []

    for item in samples:
        query = item["query"]
        ground_truth = to_canonical_intent(item["ground_truth_intent"])

        decision = await router_service.classify_intent(query, use_llm=use_llm)
        predicted = to_canonical_intent(decision.intent)

        y_true.append(ground_truth)
        y_pred.append(predicted)

        per_sample_results.append({
            "id": item.get("id"),
            "query": query,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "is_correct": ground_truth == predicted,
            "confidence": decision.confidence,
            "strategy": decision.strategy_selected,
        })

    # Compute overall accuracy
    correct_count = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    total_count = len(y_true)
    accuracy = correct_count / total_count if total_count > 0 else 0.0

    # Build confusion matrix and per-intent metrics
    confusion_matrix: Dict[str, Dict[str, int]] = {
        true_intent: {pred_intent: 0 for pred_intent in all_intents}
        for true_intent in all_intents
    }
    for yt, yp in zip(y_true, y_pred):
        if yt in confusion_matrix and yp in confusion_matrix[yt]:
            confusion_matrix[yt][yp] += 1

    per_intent_metrics: Dict[str, Dict[str, float]] = {}
    f1_list: List[float] = []

    for intent in all_intents:
        tp = confusion_matrix[intent][intent]
        fn = sum(confusion_matrix[intent][other] for other in all_intents if other != intent)
        fp = sum(confusion_matrix[other][intent] for other in all_intents if other != intent)
        support = tp + fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_intent_metrics[intent] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": support,
        }
        f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0

    return {
        "dataset": {
            "path": str(path).replace("\\", "/"),
            "sha256": sha256_hash,
            "version": metadata.get("version", "1.0.0"),
            "total_samples": total_count,
        },
        "summary": {
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "correct_count": correct_count,
            "total_count": total_count,
        },
        "per_intent": per_intent_metrics,
        "confusion_matrix": confusion_matrix,
        "samples": per_sample_results,
    }
