"""Unit tests for R6 In-House RAGAS Metrics.

Verifies:
1. compute_faithfulness (ratio of supported claims in context).
2. compute_answer_relevancy (cosine similarity between query and generated response).
3. compute_context_precision (relevant chunks appearing at top ranks).
4. compute_context_recall (ground truth key facts retrieved).
"""

import pytest
from scripts.eval_rag_generation import (
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
    split_into_claims,
)


def test_split_into_claims():
    text = "Kafka uses append-only logs. Consumer groups enable horizontal scaling! Does it handle partition rebalancing?"
    claims = split_into_claims(text)
    assert len(claims) >= 2
    assert any("append-only logs" in c for c in claims)


def test_compute_faithfulness_grounded():
    context = [
        "Kafka partitions act as an append-only commit log.",
        "Consumer groups allow multiple workers to read from distinct partitions without collisions.",
    ]
    answer = "Kafka utilizes an append-only commit log structure. Consumer groups coordinate partition reads."
    score = compute_faithfulness(answer, context)
    assert score >= 0.8


def test_compute_faithfulness_hallucinated():
    context = [
        "Kafka is a distributed streaming platform.",
    ]
    answer = "RabbitMQ uses exchanges and queues with AMQP protocol to route messages to erlang actors."
    score = compute_faithfulness(answer, context)
    assert score <= 0.4


def test_compute_answer_relevancy():
    query = "How to implement topological sort using Kahn's algorithm in Python?"
    answer = "Kahn's algorithm for topological sorting computes in-degrees of nodes and uses a queue to process nodes with zero in-degree."
    score = compute_answer_relevancy(query, answer)
    assert score > 0.65

    irrelevant = "Chocolate cake requires flour, sugar, cocoa powder, and eggs baked at 350 degrees."
    low_score = compute_answer_relevancy(query, irrelevant)
    assert low_score < 0.35


def test_compute_context_precision():
    key_facts = ["kahn algorithm", "in-degree", "queue"]
    # Relevant chunk at rank 1, irrelevant at rank 2
    chunks = [
        "Kahn algorithm maintains in-degree counts and uses a queue.",
        "Today is a sunny day in San Francisco.",
    ]
    precision = compute_context_precision(chunks, key_facts)
    assert precision == 1.0


def test_compute_context_recall():
    key_facts = ["kahn algorithm", "cycle detection", "optimistic locking"]
    # Context contains 2 of 3 key facts ('kahn algorithm' exact phrase, 'cycle detection' exact phrase)
    chunks = [
        "The kahn algorithm handles topological sorting and cycle detection for directed graphs.",
    ]
    recall = compute_context_recall(chunks, key_facts)
    assert recall == pytest.approx(0.6667, rel=1e-2)
