"""
Lead-time prediction engine.

TARGET  lead_time_recovered_days — the 0-8 day lead time recovered by the date-forensics rule
        (src/data_validation.py). DERIVED from observed fields, not a measured delivery duration.
        The previous target (lead_time_index) mostly encoded the date disguise and is no longer used.

FEATURES (known when an order is placed; no post-shipment information):
        Ship Mode, Region, Division, current_factory, distance_miles, Units, Sales,
        order_month, order_dow_rebuilt.
        Calendar fields of the disguised Order Date (order_year, order_dow) are excluded.

METHOD  * chronological split on the rebuilt original order date: 70% train / 15% validation / 15% test
        * time-ordered cross-validation (TimeSeriesSplit) inside the training set, for stability
        * model chosen on VALIDATION MAE only; if a more complex model is within 1% of a simpler one,
          the simpler one wins
        * the chosen model is refit on train+validation and scored ONCE on the untouched test set
        * baselines: overall mean, and mean per ship mode

LIMITATION  Each product is made at exactly one factory, so the data never shows the same product at
        two factories. Predictions for an alternative factory are extrapolations, and the data shows
        no measurable distance effect on lead time (see reports/PHASE1_AUDIT.md).

Run:  python -m src.prediction_engine
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import RANDOM_STATE, MODELS_TRAINED_DIR, MODELS_EVAL_DIR, RAW_DATA_PATH, PROJECT_ROOT
from src.preprocessing import run_pipeline
from src.model_components import GroupMeanRegressor

TARGET = "lead_time_recovered_days"
TARGET_LABEL = "Recovered lead time (days, derived — not measured)"
CATEGORICAL = ["Ship Mode", "Region", "Division", "current_factory"]
NUMERIC = ["distance_miles", "Units", "Sales", "order_month", "order_dow_rebuilt"]
FEATURES = CATEGORICAL + NUMERIC
SPLIT = (0.70, 0.15, 0.15)
PARSIMONY_TOLERANCE = 0.01  # prefer simpler model if within 1% validation MAE
INTERVAL_QUANTILES = (0.05, 0.95)  # empirical 90% interval from validation residuals
ACTIVE_POINTER = MODELS_TRAINED_DIR / "active_model.json"

# complexity order used by the parsimony rule (lower = simpler)
COMPLEXITY = {"baseline_mean": 0, "baseline_ship_mode_mean": 1, "linear_regression": 2,
              "gradient_boosting": 3, "random_forest": 4}


def _preprocessor():
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])


def get_model_zoo() -> dict:
    return {
        "baseline_mean": Pipeline([("model", DummyRegressor(strategy="mean"))]),
        "baseline_ship_mode_mean": Pipeline([("model", GroupMeanRegressor("Ship Mode"))]),
        "linear_regression": Pipeline([("preprocess", _preprocessor()), ("model", LinearRegression())]),
        "random_forest": Pipeline([("preprocess", _preprocessor()), ("model", RandomForestRegressor(
            n_estimators=200, max_depth=8, min_samples_leaf=20, random_state=RANDOM_STATE, n_jobs=-1))]),
        "gradient_boosting": Pipeline([("preprocess", _preprocessor()), ("model", GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE))]),
    }


def metrics(y_true, y_pred) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else float("nan"),
    }


def chronological_split(df: pd.DataFrame, split=SPLIT):
    if abs(sum(split) - 1) > 1e-9:
        raise ValueError("split fractions must sum to 1")
    df = df.sort_values(["order_seq", "Row ID"], key=lambda s: pd.to_numeric(s, errors="coerce")).reset_index(drop=True)
    n = len(df)
    a, b = int(n * split[0]), int(n * (split[0] + split[1]))
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in FEATURES + [TARGET, "order_seq", "Row ID"] if c not in df.columns]
    if missing:
        raise ValueError(f"training frame missing columns: {missing}")
    out = df.dropna(subset=FEATURES + [TARGET, "order_seq"]).copy()
    if len(out) < 50:
        raise ValueError(f"only {len(out)} usable rows; need at least 50 to train")
    return out


def select_model(val_results: dict) -> str:
    """Lowest validation MAE; a simpler model within PARSIMONY_TOLERANCE of the best wins."""
    best = min(val_results, key=lambda k: val_results[k]["mae"])
    best_mae = val_results[best]["mae"]
    candidates = [k for k, v in val_results.items() if v["mae"] <= best_mae * (1 + PARSIMONY_TOLERANCE)]
    return min(candidates, key=lambda k: COMPLEXITY.get(k, 99))


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def train_and_evaluate(df: pd.DataFrame | None = None, save: bool = True, register: bool = True,
                       version: str | None = None, cv_splits: int = 5, verbose: bool = True) -> dict:
    if df is None:
        df, _ = run_pipeline()
    data = prepare_training_frame(df)
    train_df, val_df, test_df = chronological_split(data)
    X_tr, y_tr = train_df[FEATURES], train_df[TARGET]
    X_va, y_va = val_df[FEATURES], val_df[TARGET]
    X_te, y_te = test_df[FEATURES], test_df[TARGET]

    zoo = get_model_zoo()
    results, fitted = {}, {}
    for name, pipe in zoo.items():
        # time-ordered CV inside the training period only
        cv_mae = []
        for tr_idx, va_idx in TimeSeriesSplit(n_splits=cv_splits).split(X_tr):
            m = clone(pipe).fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx])
            cv_mae.append(mean_absolute_error(y_tr.iloc[va_idx], m.predict(X_tr.iloc[va_idx])))
        model = clone(pipe).fit(X_tr, y_tr)
        fitted[name] = model
        results[name] = {
            "train": metrics(y_tr, model.predict(X_tr)),
            "validation": metrics(y_va, model.predict(X_va)),
            "cv_mae_mean": float(np.mean(cv_mae)), "cv_mae_std": float(np.std(cv_mae)),
        }

    selected = select_model({k: v["validation"] for k, v in results.items()})

    # Residual-based intervals from the VALIDATION set (model trained on train only), per ship mode.
    val_resid = y_va.to_numpy() - fitted[selected].predict(X_va)
    q_lo, q_hi = INTERVAL_QUANTILES
    resid_q = {"_all": [float(np.quantile(val_resid, q_lo)), float(np.quantile(val_resid, q_hi))]}
    for mode, idx in val_df.groupby("Ship Mode").groups.items():
        r = val_resid[val_df.index.get_indexer(idx)]
        if len(r) >= 20:
            resid_q[mode] = [float(np.quantile(r, q_lo)), float(np.quantile(r, q_hi))]

    # Permutation importance on validation (model-agnostic, uses original feature columns), for the
    # selected model and for the best non-baseline ML model (so the effect of every feature is visible
    # even when a baseline is selected).
    best_ml = min((k for k in results if not k.startswith("baseline")), key=lambda k: results[k]["validation"]["mae"])
    frames = []
    for name in dict.fromkeys([selected, best_ml]):
        perm = permutation_importance(fitted[name], X_va, y_va, n_repeats=10, random_state=RANDOM_STATE,
                                      scoring="neg_mean_absolute_error")
        frames.append(pd.DataFrame({"model": name, "feature": FEATURES,
                                    "importance_mae_increase": perm.importances_mean,
                                    "importance_std": perm.importances_std}))
    importance = (pd.concat(frames).sort_values(["model", "importance_mae_increase"], ascending=[True, False])
                  .reset_index(drop=True))

    # Test set: used ONCE. Report every candidate (trained on train only) for transparency, plus the final
    # selected model refit on train+validation. Selection above never looked at these numbers.
    for name, model in fitted.items():
        results[name]["test"] = metrics(y_te, model.predict(X_te))
    final = clone(zoo[selected]).fit(pd.concat([X_tr, X_va]), pd.concat([y_tr, y_va]))
    test_pred = final.predict(X_te)
    final_test = metrics(y_te, test_pred)

    version = version or "lt-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    meta = {
        "model_version": version,
        "selected_model": selected,
        "trained_at": dt.datetime.now().isoformat(timespec="seconds"),
        "target": TARGET, "target_label": TARGET_LABEL,
        "categorical": CATEGORICAL, "numeric": NUMERIC,
        "split": {"method": "chronological on order_date_rebuilt", "fractions": SPLIT,
                  "train_rows": len(train_df), "validation_rows": len(val_df), "test_rows": len(test_df),
                  "train_period": [str(train_df["order_date_rebuilt"].min().date()), str(train_df["order_date_rebuilt"].max().date())],
                  "validation_period": [str(val_df["order_date_rebuilt"].min().date()), str(val_df["order_date_rebuilt"].max().date())],
                  "test_period": [str(test_df["order_date_rebuilt"].min().date()), str(test_df["order_date_rebuilt"].max().date())]},
        "best_ml_model": best_ml,
        "selection_rule": f"lowest validation MAE; simpler model preferred within {PARSIMONY_TOLERANCE:.0%}",
        "results": results,
        "final_test": final_test,
        "final_fit": "selected model refit on train+validation",
        "residual_interval_quantiles": list(INTERVAL_QUANTILES),
        "residual_intervals": resid_q,
        "support_rows_by_factory": train_df.groupby("current_factory").size().astype(int).to_dict(),
        "support_rows_by_product": data.groupby("Product Name").size().astype(int).to_dict(),
        "data_file_sha256": _file_sha256(RAW_DATA_PATH),
        "library_versions": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                             "pandas": pd.__version__, "numpy": np.__version__},
        "limitations": [
            "Target is derived from disguised dates via a stated rule; it is not a measured delivery time.",
            "Each product is made at one factory only, so alternative-factory predictions are extrapolations.",
            "The data shows no measurable relationship between distance and lead time.",
        ],
    }

    if save:
        model_dir = MODELS_TRAINED_DIR / version
        eval_dir = MODELS_EVAL_DIR / version
        if model_dir.exists():
            raise FileExistsError(f"{model_dir} already exists; refusing to overwrite a saved model version")
        model_dir.mkdir(parents=True)
        eval_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(final, model_dir / "model.joblib")
        with open(model_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        with open(eval_dir / "model_comparison.json", "w") as f:
            json.dump({k: meta[k] for k in ("model_version", "selected_model", "selection_rule", "results",
                                            "final_test", "split")}, f, indent=2)
        diag = pd.DataFrame({"row_id": test_df["Row ID"].to_numpy(), "ship_mode": test_df["Ship Mode"].to_numpy(),
                             "actual": y_te.to_numpy(), "predicted": test_pred})
        diag["residual"] = diag["actual"] - diag["predicted"]
        diag.to_csv(eval_dir / "test_predictions.csv", index=False)
        importance.to_csv(eval_dir / "feature_importance.csv", index=False)
        with open(ACTIVE_POINTER, "w") as f:
            json.dump({"model_version": version,
                       "model_path": str((model_dir / "model.joblib").relative_to(PROJECT_ROOT).as_posix()),
                       "meta_path": str((model_dir / "meta.json").relative_to(PROJECT_ROOT).as_posix()),
                       "eval_dir": str(eval_dir.relative_to(PROJECT_ROOT).as_posix())}, f, indent=2)
        load_active_model.cache_clear()
        if register:
            try:
                from src.persistence import register_model_version
                register_model_version(meta, model_dir / "model.joblib")
            except Exception as exc:  # registry is best-effort; artifacts are already saved
                print(f"WARNING: model saved but not registered in database: {exc}")

    if verbose:
        _print_summary(meta)
    return {"meta": meta, "model": final, "importance": importance}


def _print_summary(meta):
    print(f"Model version {meta['model_version']} - target: {meta['target_label']}")
    print(f"{'model':26} {'cv MAE':>12} {'val MAE':>8} {'val R2':>7} {'test MAE':>9} {'test R2':>8}")
    for k, v in meta["results"].items():
        print(f"{k:26} {v['cv_mae_mean']:6.3f}+/-{v['cv_mae_std']:.3f} {v['validation']['mae']:8.3f} "
              f"{v['validation']['r2']:7.3f} {v['test']['mae']:9.3f} {v['test']['r2']:8.3f}")
    ft = meta["final_test"]
    print(f"Selected: {meta['selected_model']} ({meta['selection_rule']}). "
          f"Final test (refit on train+val): MAE {ft['mae']:.3f}, RMSE {ft['rmse']:.3f}, R2 {ft['r2']:.3f}")


# ------------------------------------------------------------------------------------------
# Inference
# ------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_active_model():
    """Returns (model, meta). Raises FileNotFoundError with a helpful message if none is trained."""
    if not ACTIVE_POINTER.exists():
        raise FileNotFoundError("No active model. Train one with: python -m src.prediction_engine")
    with open(ACTIVE_POINTER) as f:
        ptr = json.load(f)
    model = joblib.load(PROJECT_ROOT / ptr["model_path"])
    with open(PROJECT_ROOT / ptr["meta_path"]) as f:
        meta = json.load(f)
    return model, meta


def predict_lead_time(rows: pd.DataFrame) -> pd.DataFrame:
    """
    rows: DataFrame with FEATURES columns. Returns columns predicted_lead_days, interval_low, interval_high
    (empirical 90% interval from validation residuals, per ship mode when available).
    """
    model, meta = load_active_model()
    missing = [c for c in FEATURES if c not in rows.columns]
    if missing:
        raise ValueError(f"prediction input missing columns: {missing}")
    pred = model.predict(rows[FEATURES])
    iv = meta["residual_intervals"]
    lo = np.array([iv.get(m, iv["_all"])[0] for m in rows["Ship Mode"]])
    hi = np.array([iv.get(m, iv["_all"])[1] for m in rows["Ship Mode"]])
    return pd.DataFrame({"predicted_lead_days": pred,
                         "interval_low": np.maximum(pred + lo, 0), "interval_high": pred + hi},
                        index=rows.index)


if __name__ == "__main__":
    train_and_evaluate()
