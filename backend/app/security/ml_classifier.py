"""ML-based injection detection classifier using local embeddings + logistic regression."""

import logging
import os
import pickle
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class MLInjectionClassifier:
    """Classifies text for injection attempts using pre-trained ML model."""

    def __init__(self, model_path: str, embedding_model_name: str = "all-MiniLM-L6-v2", timeout_ms: int = 100):
        """Initialize the ML classifier.

        Args:
            model_path: Path to pickled logistic regression model
            embedding_model_name: Name of sentence-transformers model for embeddings
            timeout_ms: Inference timeout in milliseconds (informational only, local inference is fast)

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model_path = model_path
        self.embedding_model_name = embedding_model_name
        self.timeout_ms = timeout_ms

        # Load pickled classifier
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        # Load embedding model
        self.embedding_model = SentenceTransformer(embedding_model_name)

        logger.info(f"ML classifier initialized with model from {model_path} using {embedding_model_name}")

    def score(self, text: str) -> Optional[float]:
        """Score text for injection likelihood.

        Returns a score 0-5 where:
        - 0-2: Low suspicion (likely legitimate)
        - 2-3: Medium suspicion (borderline)
        - 3-5: High suspicion (likely injection)

        Args:
            text: Input text to score

        Returns:
            Score 0-5, or None if inference fails (will trigger fallback to heuristics)
        """
        if not text or not isinstance(text, str):
            return 0.0

        try:
            # normalize_embeddings=True puts vectors on the unit hypersphere, which
            # improves logistic regression and must match how the model was trained.
            embedding = self.embedding_model.encode([text], normalize_embeddings=True)

            # predict_proba expects shape (n_samples, n_features); encode already returns (1, dim)
            prob_injection = self.model.predict_proba(embedding)[0][1]

            # Scale 0-1 to 0-5 to match existing threshold system
            score = prob_injection * 5.0

            logger.debug(f"ML score for text: {score:.2f} (prob={prob_injection:.4f})")
            return score

        except Exception as e:
            logger.error(f"ML inference failed: {e}. Falling back to heuristics.")
            return None
