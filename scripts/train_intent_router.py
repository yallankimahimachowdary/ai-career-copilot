"""Train Intent Router with scikit-learn on train and dev splits only.

Deterministic (seed=42) and reproducible.
Outputs:
  - artifacts/models/intent_router_v1.joblib
  - artifacts/models/intent_router_v1.meta.json
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_jsonl(file_path: Path) -> List[dict]:
    items = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def build_pipeline(c_value: float, max_features_word: int = 5000, max_features_char: int = 15000) -> Pipeline:
    word_vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        sublinear_tf=True,
        max_features=max_features_word,
    )
    char_vectorizer = TfidfVectorizer(
        ngram_range=(2, 5),
        analyzer="char_wb",
        sublinear_tf=True,
        max_features=max_features_char,
    )
    union = FeatureUnion([
        ("word_tfidf", word_vectorizer),
        ("char_tfidf", char_vectorizer),
    ])
    clf = LogisticRegression(
        C=c_value,
        class_weight="balanced",
        solver="lbfgs",
        max_iter=1000,
        random_state=42,
    )
    return Pipeline([
        ("features", union),
        ("classifier", clf),
    ])


def find_optimal_threshold(y_true: np.ndarray, y_pred: np.ndarray, max_probs: np.ndarray) -> Tuple[float, float, float]:
    """Find threshold tau such that accuracy on queries with max_prob >= tau is >= 0.95."""
    best_tau = 0.50
    best_acc = 0.0
    best_cov = 0.0

    # Search candidates from 0.30 to 0.95 in 0.01 increments
    candidates = np.arange(0.30, 0.96, 0.01)
    qualifying = []

    for tau in candidates:
        mask = max_probs >= tau
        cov = float(np.mean(mask))
        if np.sum(mask) == 0:
            continue
        acc = float(accuracy_score(y_true[mask], y_pred[mask]))
        if acc >= 0.95:
            qualifying.append((tau, cov, acc))

    if qualifying:
        # Pick lowest tau that meets >= 0.95 accuracy to maximize coverage
        qualifying.sort(key=lambda x: (-x[1], x[0]))
        best_tau, best_cov, best_acc = qualifying[0]
    else:
        # Fallback: pick tau that maximizes accuracy with coverage >= 0.50
        scored = []
        for tau in candidates:
            mask = max_probs >= tau
            cov = float(np.mean(mask))
            if cov >= 0.50 and np.sum(mask) > 0:
                acc = float(accuracy_score(y_true[mask], y_pred[mask]))
                scored.append((acc, cov, tau))
        if scored:
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            acc, cov, tau = scored[0]
            best_tau, best_cov, best_acc = tau, cov, acc
        else:
            best_tau = 0.50
            mask = max_probs >= best_tau
            best_cov = float(np.mean(mask))
            best_acc = float(accuracy_score(y_true[mask], y_pred[mask])) if np.sum(mask) > 0 else 0.0

    return float(best_tau), float(best_cov), float(best_acc)


def main():
    parser = argparse.ArgumentParser(description="Train Intent Router Classifier")
    parser.add_argument("--data-dir", type=Path, default=Path("data/router"), help="Directory containing dataset splits")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/models"), help="Output directory for trained model")
    args = parser.parse_args()

    data_dir = args.data_dir
    artifacts_dir = args.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    train_path = data_dir / "train.jsonl"
    dev_path = data_dir / "dev.jsonl"
    metadata_path = data_dir / "metadata.json"

    print("=================================================================")
    print("AI Career Copilot - Intent Router Training Pipeline")
    print("=================================================================")
    print(f"Loading training data from: {train_path}")
    print(f"Loading dev data from:      {dev_path}")

    with open(train_path, "rb") as f:
        train_bytes = f.read()
    with open(dev_path, "rb") as f:
        dev_bytes = f.read()

    train_sha256 = compute_sha256(train_bytes)
    dev_sha256 = compute_sha256(dev_bytes)
    print(f"Train split SHA-256: {train_sha256}")
    print(f"Dev split SHA-256:   {dev_sha256}")

    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            expected_train_sha = meta.get("splits", {}).get("train", {}).get("sha256")
            expected_dev_sha = meta.get("splits", {}).get("dev", {}).get("sha256")
            if expected_train_sha and expected_train_sha != train_sha256:
                raise ValueError(f"Train hash mismatch! Expected {expected_train_sha}, got {train_sha256}")
            if expected_dev_sha and expected_dev_sha != dev_sha256:
                raise ValueError(f"Dev hash mismatch! Expected {expected_dev_sha}, got {dev_sha256}")
            print("Verified dataset hashes against metadata.json successfully.")

    train_data = load_jsonl(train_path)
    dev_data = load_jsonl(dev_path)

    X_train = np.array([item["query"] for item in train_data])
    y_train = np.array([item["intent"] for item in train_data])

    X_dev = np.array([item["query"] for item in dev_data])
    y_dev = np.array([item["intent"] for item in dev_data])

    print(f"Train size: {len(X_train)} samples across {len(set(y_train))} classes")
    print(f"Dev size:   {len(X_dev)} samples across {len(set(y_dev))} classes")

    # Hyperparameter Grid Search with 5-fold CV on train split
    c_candidates = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    best_c = 1.0
    best_cv_score = 0.0
    grid_results = []

    print("\nStarting 5-fold Stratified CV on train split...")
    for c in c_candidates:
        fold_scores = []
        for train_idx, val_idx in cv.split(X_train, y_train):
            pipe = build_pipeline(c_value=c)
            pipe.fit(X_train[train_idx], y_train[train_idx])
            val_preds = pipe.predict(X_train[val_idx])
            fold_f1 = f1_score(y_train[val_idx], val_preds, average="macro")
            fold_scores.append(fold_f1)
        mean_cv_f1 = float(np.mean(fold_scores))
        std_cv_f1 = float(np.std(fold_scores))

        # Also evaluate on dev split
        pipe = build_pipeline(c_value=c)
        pipe.fit(X_train, y_train)
        dev_preds = pipe.predict(X_dev)
        dev_f1 = float(f1_score(y_dev, dev_preds, average="macro"))
        dev_acc = float(accuracy_score(y_dev, dev_preds))

        grid_results.append({
            "C": c,
            "cv_macro_f1": mean_cv_f1,
            "cv_std": std_cv_f1,
            "dev_acc": dev_acc,
            "dev_macro_f1": dev_f1,
        })
        print(f"  C={c:4.1f} | 5-fold CV Macro-F1: {mean_cv_f1:.4f} (+/- {std_cv_f1:.4f}) | Dev Acc: {dev_acc:.4f} | Dev Macro-F1: {dev_f1:.4f}")

        if dev_f1 > best_cv_score:
            best_cv_score = dev_f1
            best_c = c

    print(f"\nWinning hyperparameter: C={best_c} (Dev Macro-F1: {best_cv_score:.4f})")

    # Fit best model on train, evaluate confidence calibration on dev
    dev_model = build_pipeline(c_value=best_c)
    dev_model.fit(X_train, y_train)
    dev_probs = dev_model.predict_proba(X_dev)
    dev_preds = dev_model.predict(X_dev)
    dev_max_probs = np.max(dev_probs, axis=1)

    tau, coverage_at_tau, acc_at_tau = find_optimal_threshold(y_dev, dev_preds, dev_max_probs)
    dev_acc = float(accuracy_score(y_dev, dev_preds))
    dev_macro_f1 = float(f1_score(y_dev, dev_preds, average="macro"))

    print(f"\nDev Split Evaluation:")
    print(f"  Overall Accuracy: {dev_acc * 100:.2f}%")
    print(f"  Macro-F1:         {dev_macro_f1 * 100:.2f}%")
    print(f"  Selected Tau:     {tau:.2f}")
    print(f"  Coverage at Tau:  {coverage_at_tau * 100:.2f}%")
    print(f"  Accuracy at Tau:  {acc_at_tau * 100:.2f}%")
    print("\nDev Classification Report:")
    print(classification_report(y_dev, dev_preds, digits=4))

    # Retrain on train + dev combined
    print("\nRetraining winning architecture on Train + Dev combined...")
    X_train_dev = np.concatenate([X_train, X_dev])
    y_train_dev = np.concatenate([y_train, y_dev])

    final_model = build_pipeline(c_value=best_c)
    final_model.fit(X_train_dev, y_train_dev)

    # Serialize trained model
    model_output_path = artifacts_dir / "intent_router_v1.joblib"
    joblib.dump(final_model, model_output_path, compress=3)

    with open(model_output_path, "rb") as f:
        model_bytes = f.read()
    model_sha256 = compute_sha256(model_bytes)
    print(f"Model saved to: {model_output_path}")
    print(f"Model SHA-256:  {model_sha256}")

    # Compute train+dev combined hash
    combined_bytes = train_bytes + dev_bytes
    train_dev_combined_sha256 = compute_sha256(combined_bytes)

    # Extract classes list
    classes_list = list(final_model.named_steps["classifier"].classes_)

    # Save metadata
    meta_output_path = artifacts_dir / "intent_router_v1.meta.json"
    metadata = {
        "model_name": "intent_router_v1",
        "model_type": "Tfidf_LogisticRegression",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "model_file": model_output_path.name,
        "model_sha256": model_sha256,
        "train_sha256": train_sha256,
        "dev_sha256": dev_sha256,
        "train_dev_combined_sha256": train_dev_combined_sha256,
        "classes": classes_list,
        "hyperparameters": {
            "C": best_c,
            "penalty": "l2",
            "class_weight": "balanced",
            "solver": "lbfgs",
            "max_iter": 1000,
            "feature_union": {
                "word_ngram_range": [1, 2],
                "word_max_features": 5000,
                "char_ngram_range": [2, 5],
                "char_max_features": 15000,
                "sublinear_tf": True,
            },
        },
        "validation_metrics": {
            "cv_n_splits": 5,
            "best_cv_macro_f1": float([r for r in grid_results if r["C"] == best_c][0]["cv_macro_f1"]),
            "dev_accuracy": dev_acc,
            "dev_macro_f1": dev_macro_f1,
            "tau": tau,
            "coverage_at_tau": coverage_at_tau,
            "accuracy_at_tau": acc_at_tau,
        },
        "grid_search_history": grid_results,
    }

    with open(meta_output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to: {meta_output_path}")
    print("=================================================================")
    print("Training completed successfully.")


if __name__ == "__main__":
    main()
