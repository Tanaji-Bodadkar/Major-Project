"""Group-held-out evaluation of timestamp-aligned power readings."""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.ml.preprocessing import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


def _make_pipeline(estimator) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", estimator),
    ])


def _scores(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_pred = np.maximum(np.asarray(y_pred, dtype=float), 0.0)
    return {
        "mae_w": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse_w": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4) if len(y_true) > 1 else None,
    }


def evaluate_measured_dataset(
    data: pd.DataFrame,
    test_fraction: float = 0.2,
    random_state: int = 42,
) -> tuple[dict, Pipeline, list[str]]:
    """Hold out complete sessions and compare baseline and regression candidates."""
    required = {"session_id", "measured_power_w", *FEATURE_COLUMNS}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Measured dataset is missing columns: {missing}")
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")

    frame = data.copy()
    frame["measured_power_w"] = pd.to_numeric(frame["measured_power_w"], errors="coerce")
    frame = frame[np.isfinite(frame["measured_power_w"]) & (frame["measured_power_w"] >= 0)]
    frame = frame[frame["session_id"].notna() & (frame["session_id"].astype(str).str.strip() != "")]
    for feature in FEATURE_COLUMNS:
        frame[feature] = pd.to_numeric(frame[feature], errors="coerce")
        frame.loc[~np.isfinite(frame[feature]), feature] = np.nan
    if frame.empty:
        raise ValueError("No rows have valid measured power and session_id")

    groups = frame["session_id"].astype(str).to_numpy()
    unique_groups = np.unique(groups)
    if len(unique_groups) < 3:
        raise ValueError("At least three distinct sessions are required for train/validation/test evaluation")
    if len(unique_groups) < 5:
        logger.warning("Only %d sessions are available; held-out metrics will be highly uncertain", len(unique_groups))

    outer_split = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=random_state)
    train_val_idx, test_idx = next(outer_split.split(frame, groups=groups))
    train_val_frame = frame.iloc[train_val_idx]
    train_val_groups = groups[train_val_idx]
    inner_split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_state + 1)
    train_rel_idx, validation_rel_idx = next(
        inner_split.split(train_val_frame, groups=train_val_groups)
    )
    train_idx = train_val_idx[train_rel_idx]
    validation_idx = train_val_idx[validation_rel_idx]
    train_frame = frame.iloc[train_idx]
    validation_frame = frame.iloc[validation_idx]
    test_frame = frame.iloc[test_idx]
    training_sessions = sorted(train_val_frame["session_id"].astype(str).unique().tolist())
    fit_sessions = sorted(train_frame["session_id"].astype(str).unique().tolist())
    validation_sessions = sorted(validation_frame["session_id"].astype(str).unique().tolist())
    test_groups = sorted(test_frame["session_id"].astype(str).unique().tolist())

    # Drop fields that are entirely unavailable in training; do not invent a value for them.
    feature_names = [
        name for name in FEATURE_COLUMNS
        if train_frame[name].notna().any()
    ]
    if len(feature_names) < 2:
        raise ValueError("At least two model features must have measurements in training sessions")

    X_train = train_frame[feature_names]
    X_validation = validation_frame[feature_names]
    X_test = test_frame[feature_names]
    y_train = train_frame["measured_power_w"].to_numpy(dtype=float)
    y_validation = validation_frame["measured_power_w"].to_numpy(dtype=float)
    y_test = test_frame["measured_power_w"].to_numpy(dtype=float)

    candidates = [
        ("MedianBaseline", _make_pipeline(DummyRegressor(strategy="median"))),
        ("LinearRegression", _make_pipeline(LinearRegression())),
        ("RandomForestRegressor", _make_pipeline(RandomForestRegressor(
            n_estimators=200, random_state=random_state, n_jobs=-1,
        ))),
        ("GradientBoostingRegressor", _make_pipeline(GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=random_state,
        ))),
    ]

    validation_results = []
    for name, pipeline in candidates:
        pipeline.fit(X_train, y_train)
        validation_metrics = _scores(y_validation, pipeline.predict(X_validation))
        validation_results.append({"model_name": name, **validation_metrics})
    baseline_validation_rmse = next(
        row["rmse_w"] for row in validation_results if row["model_name"] == "MedianBaseline"
    )
    best_regression = min(
        (row for row in validation_results if row["model_name"] != "MedianBaseline"),
        key=lambda row: row["rmse_w"],
    )
    selected_name = (
        best_regression["model_name"]
        if best_regression["rmse_w"] < baseline_validation_rmse
        else None
    )

    # Refit on training + validation sessions. The untouched test sessions are
    # used only once, after model selection, for the final reported score.
    X_train_val = train_val_frame[feature_names]
    y_train_val = train_val_frame["measured_power_w"].to_numpy(dtype=float)
    final_pipelines = {}
    results = []
    for name, _ in candidates:
        final_pipeline = _make_pipeline({
            "MedianBaseline": lambda: DummyRegressor(strategy="median"),
            "LinearRegression": LinearRegression,
            "RandomForestRegressor": lambda: RandomForestRegressor(
                n_estimators=200, random_state=random_state, n_jobs=-1,
            ),
            "GradientBoostingRegressor": lambda: GradientBoostingRegressor(
                n_estimators=150, learning_rate=0.05, max_depth=3, random_state=random_state,
            ),
        }[name]())
        final_pipeline.fit(X_train_val, y_train_val)
        test_metrics = _scores(y_test, final_pipeline.predict(X_test))
        validation_metrics = next(row for row in validation_results if row["model_name"] == name)
        results.append({
            "model_name": name,
            "validation_metrics": validation_metrics,
            "held_out_test_metrics": test_metrics,
        })
        final_pipelines[name] = final_pipeline
    evaluated_name = selected_name or "MedianBaseline"
    best_pipeline = final_pipelines[evaluated_name]
    best_predictions = np.maximum(best_pipeline.predict(X_test), 0.0)

    workload_metrics = {}
    if "workload_label" in test_frame:
        for label, indices in test_frame.groupby("workload_label").groups.items():
            positions = test_frame.index.get_indexer(indices)
            workload_metrics[str(label)] = _scores(y_test[positions], best_predictions[positions])

    scopes = sorted(data["measurement_scope"].dropna().astype(str).unique().tolist()) \
        if "measurement_scope" in data else []
    if len(scopes) > 1:
        raise ValueError(
            "Training data mixes measurement scopes. Evaluate one target scope per model; "
            f"found {scopes}"
        )
    cpu_package_target = scopes == ["cpu_package_power_hwinfo"]
    platform_target = scopes == ["platform_reported_power_hwinfo"]
    target_description = {
        "cpu_package_power_hwinfo": "HWiNFO CPU Package Power (CPU-domain sensor; not whole-laptop or wall-input power)",
        "platform_reported_power_hwinfo": "HWiNFO Total System Power (platform-reported estimate; not an external wall-input measurement)",
    }.get(scopes[0] if scopes else "", (
        f"Power reading in scope {scopes[0]}" if scopes
        else "Power-meter reading (scope was not recorded)"
    ))
    report = {
        "evaluation_type": (
            "hwinfo_cpu_package_group_holdout" if cpu_package_target else
            "hwinfo_platform_power_group_holdout" if platform_target else
            "real_meter_group_holdout" if not scopes else "power_reading_group_holdout"
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": "measured_power_w",
        "target_description": target_description,
        "target_unit": "W",
        "measurement_scope": scopes,
        "row_count": int(len(frame)),
        "session_count": int(len(unique_groups)),
        "training_rows": int(len(train_val_frame)),
        "fit_rows_before_validation": int(len(train_frame)),
        "validation_rows": int(len(validation_frame)),
        "test_rows": int(len(test_frame)),
        "training_sessions": training_sessions,
        "fit_sessions_before_validation": fit_sessions,
        "validation_sessions": validation_sessions,
        "held_out_sessions": test_groups,
        "features": feature_names,
        "selected_model": selected_name,
        "evaluated_model": evaluated_name,
        "selection_rule": "lowest validation-session RMSE among regression models, only if it beats the median baseline",
        "deployment_recommendation": "review_candidate" if selected_name else "do_not_deploy_no_validation_gain_over_baseline",
        "models": results,
        "workload_metrics": workload_metrics,
        "_held_out_actual_w": y_test.tolist(),
        "_held_out_predicted_w": best_predictions.tolist(),
        "_held_out_workload": test_frame["workload_label"].fillna("unlabeled").astype(str).tolist()
            if "workload_label" in test_frame else [],
        "limitations": [
            f"These scores apply only to {target_description}, the hardware, and workloads represented in the held-out sessions.",
            "The held-out split is session-level; broader hardware generalization requires additional hardware groups.",
            "HWiNFO CPU Package Power is a CPU-domain sensor and cannot validate whole-laptop or wall-input power.",
            "HWiNFO Total System Power is a platform-reported estimate and is not an external wall-input measurement.",
        ],
    }
    return report, (final_pipelines[selected_name] if selected_name else None), feature_names


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare models against timestamp-aligned power readings with complete sessions held out."
    )
    parser.add_argument("--input", default="data/processed/measured_training_data.csv")
    parser.add_argument("--report", default="reports/measured_evaluation.json")
    parser.add_argument("--candidate-dir", default="models/measured_candidate")
    parser.add_argument("--plot-dir", default="reports/measured_figures")
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    report, model, _features = evaluate_measured_dataset(frame)
    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    model_path = os.path.join(args.candidate_dir, "model.pkl")
    if model is not None:
        os.makedirs(args.candidate_dir, exist_ok=True)
        joblib.dump(model, model_path)
        report["candidate_model_file"] = model_path
    else:
        report["candidate_model_file"] = None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    y_true = np.asarray(report.pop("_held_out_actual_w"), dtype=float)
    y_pred = np.asarray(report.pop("_held_out_predicted_w"), dtype=float)
    workloads = report.pop("_held_out_workload", [])
    residuals = y_true - y_pred
    os.makedirs(args.plot_dir, exist_ok=True)
    actual_path = os.path.join(args.plot_dir, "actual_vs_predicted.png")
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(y_true, y_pred, alpha=0.55, color="#258b49", edgecolors="none")
    bounds = [float(min(y_true.min(), y_pred.min())), float(max(y_true.max(), y_pred.max()))]
    ax.plot(bounds, bounds, linestyle="--", color="#606a62", linewidth=1)
    ax.set(title=f"Held-out readings · {report['evaluated_model']}", xlabel="Observed target (W)", ylabel="Predicted target (W)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(actual_path, dpi=160)
    plt.close(fig)

    residual_path = os.path.join(args.plot_dir, "residuals.png")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(y_pred, residuals, alpha=0.55, color="#258b49", edgecolors="none")
    ax.axhline(0, linestyle="--", color="#606a62", linewidth=1)
    ax.set(title="Held-out prediction residuals", xlabel="Predicted target (W)", ylabel="Observed − predicted (W)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(residual_path, dpi=160)
    plt.close(fig)
    report["plots"] = {"actual_vs_predicted": actual_path, "residuals": residual_path}
    report_path = args.report
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Selected candidate: %s", report["selected_model"] or "none (validation failed to beat baseline)")
    logger.info("Final held-out metrics: %s", next(r["held_out_test_metrics"] for r in report["models"] if r["model_name"] == report["evaluated_model"]))
    if model is not None:
        logger.info("Model artifact: %s", model_path)
    logger.info("Evaluation report: %s", report_path)
    logger.info("Held-out plots: %s, %s", actual_path, residual_path)
    logger.info("Candidate is not activated in the live app.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()

