#!/usr/bin/env python3
"""
Train ML-based injection detector using local embeddings + logistic regression.

This script:
1. Loads training data from injection_training_set.json
2. Generates embeddings locally using sentence-transformers
3. Trains a logistic regression classifier
4. Evaluates accuracy on train/test split
5. Saves the trained model for production use

Usage:
    python backend/scripts/train_injection_classifier.py
"""

import json
import os
import pickle
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: sentence-transformers package not installed. Install with: pip install sentence-transformers")
    sys.exit(1)


def load_training_data(data_path: str) -> tuple[list[str], np.ndarray]:
    """Load and parse training data from JSON file."""
    with open(data_path, "r") as f:
        data = json.load(f)

    texts = [item["text"] for item in data]
    labels = np.array([item["label"] for item in data])

    return texts, labels


def get_embeddings(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """Generate embeddings locally using sentence-transformers."""
    print(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)

    print("Generating embeddings...")
    # normalize_embeddings=True must match inference in ml_classifier.py
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True)

    return np.array(embeddings)


def train_classifier(
    embeddings: np.ndarray,
    labels: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42
) -> tuple[LogisticRegression, dict]:
    """Train logistic regression classifier and return metrics."""
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        embeddings, labels, test_size=test_size, random_state=random_state, stratify=labels
    )

    # Train
    print("\nTraining logistic regression classifier...")
    classifier = LogisticRegression(max_iter=1000, random_state=random_state, verbose=1)
    classifier.fit(X_train, y_train)

    # Evaluate
    print("\nEvaluating on test set...")
    y_pred = classifier.predict(X_test)

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    metrics = {
        "train_accuracy": classifier.score(X_train, y_train),
        "test_accuracy": classifier.score(X_test, y_test),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }

    # Compute FPR
    metrics["fpr"] = metrics["fp"] / (metrics["fp"] + metrics["tn"]) if (metrics["fp"] + metrics["tn"]) > 0 else 0

    return classifier, metrics


def save_model(classifier: LogisticRegression, model_path: str) -> None:
    """Save trained model to disk."""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(classifier, f)
    print(f"\n✓ Model saved to {model_path}")


def print_metrics(metrics: dict) -> None:
    """Print evaluation metrics in a readable format."""
    print("\n" + "=" * 60)
    print("CLASSIFIER METRICS")
    print("=" * 60)
    print(f"Train Accuracy: {metrics['train_accuracy']:.4f}")
    print(f"Test Accuracy:  {metrics['test_accuracy']:.4f}")
    print(f"Precision:      {metrics['precision']:.4f} (TP / (TP + FP))")
    print(f"Recall (TPR):   {metrics['recall']:.4f} (TP / (TP + FN))  ← Target >0.90")
    print(f"FPR:            {metrics['fpr']:.4f} (FP / (FP + TN))    ← Target <0.05")
    print(f"F1 Score:       {metrics['f1']:.4f}")
    print("\n" + "-" * 60)
    print("CONFUSION MATRIX")
    print("-" * 60)
    print(f"True Negatives:  {metrics['tn']} (legitimate, correctly passed)")
    print(f"False Positives: {metrics['fp']} (legitimate, incorrectly blocked)")
    print(f"False Negatives: {metrics['fn']} (injection, incorrectly passed)")
    print(f"True Positives:  {metrics['tp']} (injection, correctly blocked)")
    print("=" * 60)

    # Pass/fail on criteria
    tpr_ok = metrics['recall'] >= 0.90
    fpr_ok = metrics['fpr'] <= 0.05

    print(f"\n{'✓' if tpr_ok else '✗'} TPR >= 0.90? {metrics['recall']:.4f}")
    print(f"{'✓' if fpr_ok else '✗'} FPR <= 0.05? {metrics['fpr']:.4f}")

    if tpr_ok and fpr_ok:
        print("\n✓ MODEL MEETS SUCCESS CRITERIA")
    else:
        print("\n✗ MODEL DOES NOT MEET SUCCESS CRITERIA (see gaps above)")


def main() -> None:
    """Main training pipeline."""
    # Paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    data_file = repo_root / "data" / "injection_training_set.json"
    model_file = repo_root / "data" / "injection_model.pkl"

    if not data_file.exists():
        print(f"Error: Training data not found at {data_file}")
        sys.exit(1)

    print("=" * 60)
    print("TRAINING ML-BASED INJECTION DETECTOR")
    print("=" * 60)

    # Load training data
    print(f"\nLoading training data from {data_file}...")
    texts, labels = load_training_data(str(data_file))
    print(f"✓ Loaded {len(texts)} examples ({np.sum(labels)} injections, {len(labels) - np.sum(labels)} legitimate)")

    # Get embeddings (local, no API needed)
    print("\nGenerating local embeddings...")
    embeddings = get_embeddings(texts)
    print(f"✓ Generated {len(embeddings)} embeddings, dimension: {embeddings.shape[1]}")

    # Train classifier
    classifier, metrics = train_classifier(embeddings, labels)

    # Print metrics
    print_metrics(metrics)

    # Save model
    save_model(classifier, str(model_file))

    print("\n✓ Training complete!")


if __name__ == "__main__":
    main()
