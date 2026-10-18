"""Load curated interview corpus into ChromaDB interview_material_embeddings collection.

Idempotent loader:
1. Reads data/interview_corpus/interview_corpus_v1.jsonl.
2. Encodes questions using local SentenceTransformer (all-MiniLM-L6-v2, 384 dim).
3. Upserts into ChromaDB interview_material_embeddings with metadata:
   - corpus_id, role_family, question_type, difficulty, skill_tags, source, key_points_json.
4. Reports total collection count and verify idempotence on re-run.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.chroma import chroma_service, get_interview_material_collection
from app.services.embedding_service import get_sentence_transformer

CORPUS_PATH = Path("data/interview_corpus/interview_corpus_v1.jsonl")


def load_corpus_into_chroma():
    print(f"Reading interview corpus from {CORPUS_PATH}...")
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(items)} interview items.")

    print("Loading SentenceTransformer model...")
    model = get_sentence_transformer()

    # Prepare texts to embed
    embed_texts = []
    ids = []
    documents = []
    metadatas = []

    for item in items:
        cid = item["id"]
        q_text = item["question"]
        family = item.get("role_family", "general")
        qtype = item.get("question_type", "technical")
        diff = item.get("difficulty", "mid")
        tags = item.get("skill_tags", [])
        tags_str = ", ".join(tags)
        pts = item.get("key_points", [])
        pts_str = "; ".join(pts)

        # Composite rich text for semantic retrieval
        composite = (
            f"Question: {q_text}\n"
            f"Role Family: {family}\n"
            f"Question Type: {qtype}\n"
            f"Skills: {tags_str}\n"
            f"Key Points: {pts_str}"
        )
        embed_texts.append(composite)
        ids.append(cid)
        documents.append(q_text)
        metadatas.append({
            "corpus_id": cid,
            "role_family": family,
            "question_type": qtype,
            "difficulty": diff,
            "skill_tags": tags_str,
            "source": item.get("source", "curated_seed"),
            "key_points_json": json.dumps(pts),
        })

    print(f"Encoding {len(embed_texts)} items with sentence-transformers...")
    embeddings = model.encode(embed_texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
    embeddings_list = [emb.tolist() for emb in embeddings]

    print("Upserting into ChromaDB interview_material_embeddings collection...")
    chroma_service.upsert_interview_material(
        ids=ids,
        embeddings=embeddings_list,
        documents=documents,
        metadatas=metadatas,
    )

    col = get_interview_material_collection()
    total_count = col.count()

    print("\n--- CHROMA INTERVIEW CORPUS LOAD SUMMARY ---")
    print(f"  Items processed : {len(items)}")
    print(f"  Collection size  : {total_count}")
    print("Interview corpus loading complete.")


if __name__ == "__main__":
    load_corpus_into_chroma()
