"""
Carbon Intelligence Platform — Model Evaluation and Visualization

Generates evaluation plots for the trained power estimation models.
Saves plots to reports/figures/.

Usage (standalone):
    python -m app.ml.evaluate
"""

import os
import sys
import logging
import numpy as np

logger = logging.getLogger(__name__)


def generate_evaluation_plots(models_to_train, X_test, y_test, results, best_name, config):
    """
    Generate and save evaluation plots.

    Args:
        models_to_train: list of (name, model) tuples
        X_test: scaled test features
        y_test: true power values
        results: list of result dicts from evaluate_model()
        best_name: name of the best model
        config: app config object
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend for server-side rendering
        import matplotlib.pyplot as plt
        import seaborn as sns

        figures_dir = os.path.join(config.REPORTS_DIR, "figures")
        os.makedirs(figures_dir, exist_ok=True)

        # Style
        sns.set_theme(style="whitegrid", palette="muted")

        # Find best model object
        best_model = None
        for name, model in models_to_train:
            if name == best_name:
                best_model = model
                break

        if best_model is not None:
            y_pred_best = best_model.predict(X_test)

            # --------------------------------------------------------
            # 1. Synthetic target vs predicted
            # --------------------------------------------------------
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.scatter(y_test, y_pred_best, alpha=0.4, s=20, label="Samples")
            min_val = min(y_test.min(), y_pred_best.min())
            max_val = max(y_test.max(), y_pred_best.max())
            ax.plot([min_val, max_val], [min_val, max_val], "r--", label="Perfect prediction")
            ax.set_xlabel("Synthetic target (W)")
            ax.set_ylabel("Predicted Power (W)")
            ax.set_title(f"Synthetic Target vs Predicted Power — {best_name}")
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(figures_dir, "actual_vs_predicted.png"), dpi=150)
            plt.close()
            logger.info("Saved: actual_vs_predicted.png")

            # --------------------------------------------------------
            # 2. Residuals
            # --------------------------------------------------------
            residuals = y_pred_best - y_test
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))

            axes[0].scatter(y_pred_best, residuals, alpha=0.4, s=20)
            axes[0].axhline(0, color="r", linestyle="--")
            axes[0].set_xlabel("Predicted Power (W)")
            axes[0].set_ylabel("Residual (W)")
            axes[0].set_title("Residuals vs Predicted")

            axes[1].hist(residuals, bins=40, edgecolor="white")
            axes[1].axvline(0, color="r", linestyle="--")
            axes[1].set_xlabel("Residual (W)")
            axes[1].set_ylabel("Count")
            axes[1].set_title("Residual Distribution")

            plt.suptitle(f"Synthetic Target Residual Analysis — {best_name}")
            plt.tight_layout()
            plt.savefig(os.path.join(figures_dir, "residuals.png"), dpi=150)
            plt.close()
            logger.info("Saved: residuals.png")

            # --------------------------------------------------------
            # 3. Feature Importance (RF / GBR)
            # --------------------------------------------------------
            from app.ml.preprocessing import FEATURE_COLUMNS
            if hasattr(best_model, "feature_importances_"):
                importances = best_model.feature_importances_
                indices = np.argsort(importances)[::-1]
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.bar(
                    range(len(FEATURE_COLUMNS)),
                    importances[indices],
                    align="center",
                    color=sns.color_palette("muted")[0],
                )
                ax.set_xticks(range(len(FEATURE_COLUMNS)))
                ax.set_xticklabels(
                    [FEATURE_COLUMNS[i] for i in indices], rotation=45, ha="right"
                )
                ax.set_xlabel("Feature")
                ax.set_ylabel("Importance")
                ax.set_title(f"Feature Importance — {best_name}")
                plt.tight_layout()
                plt.savefig(os.path.join(figures_dir, "feature_importance.png"), dpi=150)
                plt.close()
                logger.info("Saved: feature_importance.png")

        # --------------------------------------------------------
        # 4. Model Comparison Bar Chart
        # --------------------------------------------------------
        names = [r["model_name"].replace("Regressor", "\nRegressor") for r in results]
        maes = [r["mae_w"] for r in results]
        rmses = [r["rmse_w"] for r in results]
        r2s = [r["r2"] for r in results]

        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        colors = sns.color_palette("muted", len(names))

        axes[0].bar(names, maes, color=colors)
        axes[0].set_title("MAE (W) — lower is better")
        axes[0].set_ylabel("MAE (W)")

        axes[1].bar(names, rmses, color=colors)
        axes[1].set_title("RMSE (W) — lower is better")
        axes[1].set_ylabel("RMSE (W)")

        axes[2].bar(names, r2s, color=colors)
        axes[2].set_title("R² — higher is better")
        axes[2].set_ylabel("R²")
        axes[2].set_ylim(0, 1)

        plt.suptitle("Model Comparison — Synthetic Targets; Not Real-World Accuracy")
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, "model_comparison.png"), dpi=150)
        plt.close()
        logger.info("Saved: model_comparison.png")

        logger.info(f"All evaluation plots saved to: {figures_dir}")

    except ImportError as e:
        logger.warning(f"Matplotlib/Seaborn not available for plots: {e}")
    except Exception as e:
        logger.error(f"Error generating evaluation plots: {e}")


if __name__ == "__main__":
    # Standalone evaluation — requires model and data to already exist
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config import get_config
    import joblib
    import pandas as pd
    from app.ml.preprocessing import prepare_training_features, FEATURE_COLUMNS

    cfg = get_config()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Load saved model and scaler
    model = joblib.load(cfg.MODEL_FILE)
    scaler = joblib.load(cfg.PREPROCESSING_FILE)
    import json
    with open(cfg.METADATA_FILE) as f:
        metadata = json.load(f)

    # Load dataset and recreate test split
    data_path = os.path.join(cfg.DATA_DIR, "processed", "training_data.csv")
    df = pd.read_csv(data_path)
    X_df = prepare_training_features(df)
    y = df["measured_power_w"].values.astype(float)
    from sklearn.model_selection import train_test_split
    _, X_test_df, _, y_test = train_test_split(
        X_df, y, test_size=0.2, random_state=42
    )
    X_test = scaler.transform(X_test_df)

    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y_pred = model.predict(X_test)
    result = {
        "model_name": metadata["model_name"],
        "mae_w": float(mean_absolute_error(y_test, y_pred)),
        "rmse_w": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
        "predictions": y_pred,
    }
    print(f"\nModel: {result['model_name']}")
    print(f"MAE:   {result['mae_w']:.3f} W")
    print(f"RMSE:  {result['rmse_w']:.3f} W")
    print(f"R²:    {result['r2']:.4f}")

    generate_evaluation_plots(
        models_to_train=[(metadata["model_name"], model)],
        X_test=X_test,
        y_test=y_test,
        results=[result],
        best_name=metadata["model_name"],
        config=cfg,
    )

