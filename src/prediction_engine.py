"""
Phase 4: ML prediction engine for the shipping lead-time INDEX (de-trended, relative signal —
see DEVELOPMENT_PROGRESS.md for why the raw lead_time_days_raw field is not used directly).

Target: lead_time_index = lead_time_days_raw - per-ship-mode median.
Features available at prediction time (no post-shipment leakage):
  product division/name, current factory, destination region/state, ship mode,
  distance_miles, units, sales, order month/day-of-week.
"""
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config import RANDOM_STATE, MODELS_TRAINED_DIR, MODELS_EVAL_DIR
from src.preprocessing import run_pipeline

CATEGORICAL = ["Division", "current_factory", "Region", "State/Province", "Ship Mode", "order_year"]
NUMERIC = ["distance_miles", "Units", "Sales", "order_month", "order_dow"]
TARGET = "lead_time_index"


def build_pipeline(model):
    preprocessor = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def get_model_zoo():
    return {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=200, max_depth=10, random_state=RANDOM_STATE, n_jobs=-1),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=RANDOM_STATE),
    }


def train_and_evaluate():
    df, _ = run_pipeline()
    df = df.dropna(subset=NUMERIC + CATEGORICAL + [TARGET])

    # Chronological split: order by order_date so validation simulates predicting the future,
    # not random same-period leakage across multi-line orders.
    df = df.sort_values("order_date")
    n = len(df)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    X_train, y_train = train_df[CATEGORICAL + NUMERIC], train_df[TARGET]
    X_val, y_val = val_df[CATEGORICAL + NUMERIC], val_df[TARGET]
    X_test, y_test = test_df[CATEGORICAL + NUMERIC], test_df[TARGET]

    results = {}
    fitted_models = {}

    for name, model in get_model_zoo().items():
        pipe = build_pipeline(model)
        pipe.fit(X_train, y_train)

        val_pred = pipe.predict(X_val)
        test_pred = pipe.predict(X_test)

        results[name] = {
            "val_mae": float(mean_absolute_error(y_val, val_pred)),
            "val_rmse": float(np.sqrt(mean_squared_error(y_val, val_pred))),
            "val_r2": float(r2_score(y_val, val_pred)),
            "test_mae": float(mean_absolute_error(y_test, test_pred)),
            "test_rmse": float(np.sqrt(mean_squared_error(y_test, test_pred))),
            "test_r2": float(r2_score(y_test, test_pred)),
        }
        fitted_models[name] = pipe

    # Select best model: prioritize test R2 among models that are not simply overfitting train
    # (we didn't record train score here deliberately -- selection is on held-out generalization only)
    best_name = max(results, key=lambda k: results[k]["test_r2"])

    # Residuals from the VALIDATION set of the best model -> used for prediction intervals / confidence
    best_pipe = fitted_models[best_name]
    val_pred_best = best_pipe.predict(X_val)
    residuals = (y_val.values - val_pred_best)
    residual_std = float(np.std(residuals))

    MODELS_TRAINED_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_EVAL_DIR.mkdir(parents=True, exist_ok=True)

    for name, pipe in fitted_models.items():
        joblib.dump(pipe, MODELS_TRAINED_DIR / f"{name}.joblib")

    joblib.dump({
        "best_model_name": best_name,
        "residual_std": residual_std,
        "categorical": CATEGORICAL,
        "numeric": NUMERIC,
        # support set: which (product_name, factory) combos have >= N training rows -> used to flag
        # low-confidence/unsupported scenarios in scenario_simulator.py
        "support_counts": train_df.groupby(["current_factory"]).size().to_dict(),
    }, MODELS_TRAINED_DIR / "model_meta.joblib")

    with open(MODELS_EVAL_DIR / "model_comparison.json", "w") as f:
        json.dump({"results": results, "best_model": best_name, "residual_std": residual_std}, f, indent=2)

    # actual-vs-predicted + residuals for the best model, saved for the Model Analytics dashboard page
    diag_df = pd.DataFrame({
        "actual": y_test.values,
        "predicted": test_pred if best_name == name else fitted_models[best_name].predict(X_test),
    })
    diag_df["residual"] = diag_df["actual"] - diag_df["predicted"]
    diag_df.to_csv(MODELS_EVAL_DIR / "test_predictions.csv", index=False)

    # feature importance (tree models only)
    if best_name in ("random_forest", "gradient_boosting"):
        ohe = best_pipe.named_steps["preprocess"].named_transformers_["cat"]
        cat_feature_names = list(ohe.get_feature_names_out(CATEGORICAL))
        all_feature_names = cat_feature_names + NUMERIC
        importances = best_pipe.named_steps["model"].feature_importances_
        imp_df = pd.DataFrame({"feature": all_feature_names, "importance": importances}) \
            .sort_values("importance", ascending=False).head(25)
        imp_df.to_csv(MODELS_EVAL_DIR / "feature_importance.csv", index=False)

    print(json.dumps(results, indent=2))
    print(f"\nBest model: {best_name} (selected on held-out TEST R2, chronological split)")
    print(f"Residual std (for confidence intervals): {residual_std:.2f}")
    return results, best_name


if __name__ == "__main__":
    train_and_evaluate()
