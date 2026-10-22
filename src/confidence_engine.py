"""
Confidence / reliability scoring. No arbitrary confidence percentages — everything here is
derived from actual validation evidence (residual std, support counts, model R2).
"""
import joblib
from src.config import MODELS_TRAINED_DIR, MODELS_EVAL_DIR
import json

MIN_SUPPORT_ROWS = 30  # below this many historical rows for a factory, flag "unsupported"


def load_model_meta():
    return joblib.load(MODELS_TRAINED_DIR / "model_meta.joblib")


def load_eval():
    with open(MODELS_EVAL_DIR / "model_comparison.json") as f:
        return json.load(f)


def confidence_label(factory_name: str) -> dict:
    """
    Returns a dict: {label, reason, support_rows, model_test_r2}
    label in {"unsupported", "low", "moderate"}  -- note: "high" is intentionally never
    issued for this dataset, because the overall model R2 is near zero (documented finding).
    """
    meta = load_model_meta()
    eval_results = load_eval()
    support = meta["support_counts"].get(factory_name, 0)
    best_model = eval_results["best_model"]
    test_r2 = eval_results["results"][best_model]["test_r2"]

    if support < MIN_SUPPORT_ROWS:
        return {
            "label": "unsupported",
            "reason": f"Only {support} historical training rows for {factory_name}; "
                      f"below the minimum of {MIN_SUPPORT_ROWS} rows needed to trust a prediction.",
            "support_rows": support,
            "model_test_r2": test_r2,
        }

    # Because overall held-out R2 is ~0-0.04 (documented in reports/model_evaluation),
    # no prediction from this model should be presented as reliable. Capped at "low".
    return {
        "label": "low",
        "reason": f"{support} historical rows support this factory, but the best model's held-out "
                  f"test R2 is only {test_r2:.3f} (near zero), because the underlying lead-time field "
                  f"is itself a corrupted/synthetic signal (see DEVELOPMENT_PROGRESS.md). All predictions "
                  f"from this model should be treated as directional at best, not decision-grade on their own.",
        "support_rows": support,
        "model_test_r2": test_r2,
    }
