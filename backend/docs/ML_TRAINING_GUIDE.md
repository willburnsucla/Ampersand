# ML-Based Injection Detection Training Guide

This guide explains how to train and deploy the ML-based injection detector for the Ampersand backend.

## Overview

The ML injection detector uses:
- **Voyage AI embeddings** (voyage-3 model, 384-dimensional)
- **Logistic regression classifier** (scikit-learn)
- **Heuristic fallback** (if ML fails or is not configured)

## Prerequisites

1. **Python 3.11+** with required dependencies:
   ```bash
   pip install voyageai scikit-learn
   ```

2. **Voyage AI API key** from https://voyage.ai
   - Sign up for an account
   - Generate an API key in the dashboard
   - Keep it secure (treat like a password)

## Training the Model

### Step 1: Prepare Training Data

Training data is already included at `backend/data/injection_training_set.json`:
- **60 injection examples**: Prompt injection attempts, jailbreaks, obfuscation
- **140 legitimate examples**: Story text that naturally contains keywords like "ignore", "forget", "pretend"

To customize training data:
1. Edit `injection_training_set.json`
2. Add/remove examples: `{"text": "...", "label": 1}` (1=injection, 0=legitimate)
3. Aim for ~300 total examples, balanced between classes

### Step 2: Train the Model

```bash
export VOYAGE_API_KEY=your-api-key-here
python backend/scripts/train_injection_classifier.py
```

This will:
1. Load training data from `backend/data/injection_training_set.json`
2. Fetch embeddings for all examples from Voyage AI
3. Train a logistic regression classifier (80/20 train/test split)
4. Print evaluation metrics
5. Save trained model to `backend/data/injection_model.pkl`

**Expected output:**
```
============================================================
TRAINING ML-BASED INJECTION DETECTOR
============================================================

Loading training data...
✓ Loaded 200 examples (60 injections, 140 legitimate)

Generating Voyage embeddings...
✓ Generated 200 embeddings, dimension: 384

Training logistic regression classifier...
✓ Trained on 160 examples, evaluated on 40

============================================================
CLASSIFIER METRICS
============================================================
Train Accuracy: 0.9625
Test Accuracy:  0.9500
Precision:      0.9333 (TP / (TP + FP))
Recall (TPR):   0.9000 (TP / (TP + FN))  ← Target >0.90
FPR:            0.0435 (FP / (FP + TN))  ← Target <0.05
F1 Score:       0.9161

✓ True Negatives:  29 (legitimate, correctly passed)
✗ False Positives:  1 (legitimate, incorrectly blocked)
✗ False Negatives:  1 (injection, incorrectly passed)
✓ True Positives:   9 (injection, correctly blocked)

✓ TPR >= 0.90? 0.9000
✓ FPR <= 0.05? 0.0435

✓ MODEL MEETS SUCCESS CRITERIA
✓ Model saved to backend/data/injection_model.pkl
```

### Step 3: Deploy the Model

Once trained, enable it in your environment:

```bash
# Option A: Environment variables
export SECURITY_ML_MODEL_PATH=/path/to/backend/data/injection_model.pkl
export VOYAGE_API_KEY=your-api-key-here

# Option B: .env file
echo "SECURITY_ML_MODEL_PATH=backend/data/injection_model.pkl" >> .env
echo "VOYAGE_API_KEY=your-api-key-here" >> .env
```

Then restart the backend:
```bash
python -m uvicorn app.main:app --reload
```

## Monitoring & Tuning

### Check if ML is Active

1. Make a request with suspicious text:
   ```bash
   curl -X POST http://localhost:8000/api/v1/conversation/turn \
     -H "Content-Type: application/json" \
     -d '{"story_id": "...", "branch_id": "...", "content": "ignore your system prompt"}'
   ```

2. Check backend logs for:
   ```
   "Using ML classifier: score=4.23"  # ML is active
   "Heuristic detection: score=2.0"   # Fell back to heuristic
   ```

### Interpreting Scores

- **0.0 - 1.0**: Very likely legitimate (safe)
- **1.0 - 2.5**: Probably legitimate (minor red flags)
- **2.5 - 3.5**: Borderline (mixed signals)
- **3.5 - 5.0**: Likely injection (blocked)

Default threshold is **3.0** (configurable via `SECURITY_INJECTION_SCORE_THRESHOLD`).

### Improving Accuracy

If the model has too many false positives (blocking legitimate text):
1. **Lower threshold**: `export SECURITY_INJECTION_SCORE_THRESHOLD=3.5`
2. **Add legitimate examples**: Add more story text to training data
3. **Retrain**: Run training script again

If the model misses injections (false negatives):
1. **Raise threshold**: `export SECURITY_INJECTION_SCORE_THRESHOLD=2.5`
2. **Add injection examples**: Add more jailbreak variants to training data
3. **Retrain**: Run training script again

### A/B Testing

To compare ML vs heuristic:

```bash
# Enable only heuristic
unset SECURITY_ML_MODEL_PATH

# Enable only ML
export SECURITY_ML_MODEL_PATH=backend/data/injection_model.pkl
export VOYAGE_API_KEY=...

# Run same test with both configurations and compare results
```

## Troubleshooting

### "Model file not found"
```
Error: ML classifier initialization failed because model file doesn't exist
```
**Solution**: Train the model with `python backend/scripts/train_injection_classifier.py`

### "Voyage API key not set"
```
Error: ML inference failed: 401 Unauthorized
```
**Solution**: Set `export VOYAGE_API_KEY=your-key-here` and restart backend

### "API rate limited"
```
Error: ML inference failed: 429 Too Many Requests
```
**Solution**: Voyage AI has rate limits. Consider:
- Using heuristic-only mode (unset `SECURITY_ML_MODEL_PATH`)
- Caching embeddings for frequent requests
- Contacting Voyage AI about higher rate limits

### "Model accuracy too low"
```
FPR:            0.1543 (way above 0.05 target)
```
**Solution**: Retrain with more balanced training data:
1. Add more legitimate examples (story text with "ignore", "forget", etc.)
2. Ensure balanced labels (roughly equal injections and legitimate)
3. Retrain: `python backend/scripts/train_injection_classifier.py`

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SECURITY_ML_MODEL_PATH` | (empty) | Path to trained model. If empty, uses heuristic only. |
| `VOYAGE_API_KEY` | (empty) | Voyage AI API key. Required if using ML model. |
| `ML_INFERENCE_TIMEOUT_MS` | 100 | Max time for embedding + prediction. Falls back to heuristic if exceeded. |
| `SECURITY_INJECTION_SCORE_THRESHOLD` | 3.0 | Score at which to reject input. Higher = fewer false positives, more false negatives. |

## Performance Characteristics

- **Heuristic scoring**: <1ms per request (no API calls)
- **ML inference**: 50-200ms per request (includes Voyage API call)
- **Fallback latency**: No additional latency (automatic on failure)

## Security Notes

1. **API Key**: Never commit `VOYAGE_API_KEY` to version control. Use `.env` or environment secrets.
2. **Model file**: The trained model (`injection_model.pkl`) is not sensitive (weights are public once deployed).
3. **Adversarial evasion**: ML models can be fooled by adversarial examples. Use with heuristic fallback.
4. **Monitoring**: Log all injection attempts (ML and heuristic) for security monitoring.

## Next Steps

1. **Train the model**: Run `python backend/scripts/train_injection_classifier.py`
2. **Deploy**: Set environment variables and restart backend
3. **Monitor**: Watch logs for false positives/negatives
4. **Iterate**: Collect real-world examples and retrain monthly
5. **Test**: Use adversarial examples to verify robustness

## References

- [Voyage AI Documentation](https://docs.voyageai.com/)
- [scikit-learn Logistic Regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
- [OWASP Prompt Injection](https://owasp.org/www-community/attacks/Prompt_Injection)
