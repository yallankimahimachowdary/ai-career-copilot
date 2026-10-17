"""Leakage verification script between train, dev, and test splits for the intent router dataset."""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing, stripping punctuation, and collapsing whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def get_token_trigrams(normalized_text: str) -> Set[str]:
    """Compute word trigrams; fallback to character 4-grams for very short queries."""
    tokens = normalized_text.split()
    if len(tokens) >= 3:
        return {" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)}
    # For short queries with < 3 tokens, compute character 4-grams to catch near-duplicates
    clean_chars = "".join(tokens)
    if len(clean_chars) >= 4:
        return {clean_chars[i : i + 4] for i in range(len(clean_chars) - 3)}
    return {clean_chars} if clean_chars else set()


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def load_split(file_path: Path) -> List[dict]:
    if not file_path.exists():
        raise FileNotFoundError(f"Split file not found: {file_path}")
    if file_path.suffix == ".jsonl":
        items = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items
    elif file_path.suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("samples", data)
    raise ValueError(f"Unsupported format: {file_path}")


def check_splits(data_dir: Path, threshold: float = 0.7) -> bool:
    splits = {
        "train": load_split(data_dir / "train.jsonl"),
        "dev": load_split(data_dir / "dev.jsonl"),
        "test": load_split(data_dir / "test.jsonl"),
    }

    print(f"Loaded splits from {data_dir}:")
    for name, items in splits.items():
        print(f"  - {name}: {len(items)} samples")

    pairs_to_check = [("train", "dev"), ("train", "test"), ("dev", "test")]
    violations: List[Tuple[str, str, dict, dict, float, str]] = []

    for name1, name2 in pairs_to_check:
        items1 = splits[name1]
        items2 = splits[name2]

        # 1. Exact normalized matches
        norm_map1 = {normalize_text(item["query"]): item for item in items1}
        for item2 in items2:
            norm2 = normalize_text(item2["query"])
            if norm2 in norm_map1:
                item1 = norm_map1[norm2]
                violations.append((name1, name2, item1, item2, 1.0, "EXACT_DUPLICATE"))

        # 2. Token-trigram Jaccard similarity >= threshold
        trigrams1 = [(item, get_token_trigrams(normalize_text(item["query"]))) for item in items1]
        for item2 in items2:
            trigrams2 = get_token_trigrams(normalize_text(item2["query"]))
            if not trigrams2:
                continue
            for item1, tri1 in trigrams1:
                if not tri1:
                    continue
                sim = jaccard_similarity(tri1, trigrams2)
                if sim >= threshold:
                    violations.append((name1, name2, item1, item2, sim, "TRIGRAM_JACCARD_OVERLAP"))

    if violations:
        print(f"\n[ERROR] Found {len(violations)} leakage violation(s) across splits:")
        for name1, name2, it1, it2, score, vtype in violations[:20]:
            print(f"  [{vtype}] {name1} vs {name2} (Score: {score:.3f}):")
            print(f"    {name1} [{it1.get('id')}]: \"{it1.get('query')}\"")
            print(f"    {name2} [{it2.get('id')}]: \"{it2.get('query')}\"")
        return False

    print("\n[SUCCESS] No leakage detected across splits. 0 exact duplicates and 0 pairs with trigram Jaccard >= 0.70.")
    return True


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    router_data_dir = repo_root / "data" / "router"
    success = check_splits(router_data_dir)
    sys.exit(0 if success else 1)
