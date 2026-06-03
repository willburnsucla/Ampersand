"""ML-based injection detection classifier using Voyage embeddings + logistic regression."""

import logging
import os
import pickle
from typing import Optional

from voyageai import Client

logger = logging.getLogger(__name__)


class MLInjectionClassifier:
    """Classifies text for injection attempts using pre-trained ML model."""

    def __init__(self, model_path: str, voyage_api_key: str, timeout_ms: int = 100):
        """Initialize the ML classifier.

        Args:
            model_path: Path to pickled logistic regression model
            voyage_api_key: Voyage AI API key for embeddings
            timeout_ms: Inference timeout in milliseconds

        Raises:
            FileNotFoundError: If model file doesn't exist
            ValueError: If API key is empty
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        if not voyage_api_key:
            raise ValueError("Voyage API key is required")

        self.model_path = model_path
        self.voyage_api_key = voyage_api_key
        self.timeout_ms = timeout_ms

        # Load model
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        # Initialize Voyage client
        self.client = Client(api_key=voyage_api_key)

        logger.info(f"ML classifier initialized with model from {model_path}")

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
            # Get embedding from Voyage
            response = self.client.embed(
                texts=[text],
                model="voyage-3",
                input_type="query"
            )
            embedding = response.embeddings[0]

            # Get probability from classifier
            # model.predict_proba returns [[prob_negative, prob_positive]]
            prob_injection = self.model.predict_proba([embedding])[0][1]

            # Scale 0-1 to 0-5 to match existing threshold system
            score = prob_injection * 5.0

            logger.debug(f"ML score for text: {score:.2f} (prob={prob_injection:.4f})")
            return score

        except Exception as e:
            logger.error(f"ML inference failed: {e}. Falling back to heuristics.")
            return None
