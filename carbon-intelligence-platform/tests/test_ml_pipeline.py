import os
import json

import numpy as np
import pandas as pd
import pytest

from app.ml.preprocessing import FEATURE_COLUMNS, prepare_training_features
from app.ml.train import load_dataset


def test_training_dataset_validation_rejects_missing_column(tmp_path):
    path = tmp_path / "dataset.csv"
    pd.DataFrame({"measured_power_w": [10.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(str(path))


def test_training_dataset_validation_rejects_negative_target(tmp_path):
    row = {column: 1.0 for column in FEATURE_COLUMNS}
    row["measured_power_w"] = -1.0
    path = tmp_path / "dataset.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="negative power"):
        load_dataset(str(path))


def test_training_features_preserve_missingness_and_feature_order():
    row = {column: 1.0 for column in FEATURE_COLUMNS}
    row["gpu_utilization_pct"] = np.nan
    features = prepare_training_features(pd.DataFrame([row]))
    assert list(features.columns) == FEATURE_COLUMNS
    assert np.isnan(features.loc[0, "gpu_utilization_pct"])


def test_saved_preprocessing_pipeline_transforms_consistently(tmp_path):
    import joblib
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    train = pd.DataFrame(np.arange(45, dtype=float).reshape(5, 9), columns=FEATURE_COLUMNS)
    train.iloc[0, 0] = np.nan
    pipeline = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    fitted = pipeline.fit(train)
    expected = fitted.transform(train.iloc[[0]])
    path = tmp_path / "preprocessing.pkl"
    joblib.dump(fitted, path)
    loaded = joblib.load(path)
    np.testing.assert_allclose(loaded.transform(train.iloc[[0]]), expected)


def test_live_prediction_imputes_and_discloses_unavailable_gpu(monkeypatch):
    from tests.test_telemetry import make_test_snapshot
    from app.ml import model_loader
    from app.ml.predict import predict_power
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    class ConstantModel:
        def predict(self, matrix):
            return np.array([75.0])

    snapshot = make_test_snapshot()
    model_loader._model = ConstantModel()
    model_loader._pipeline = Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler())]).fit(
        pd.DataFrame([[1.0] * 9, [2.0] * 9], columns=FEATURE_COLUMNS)
    )
    model_loader._metadata = {"features": FEATURE_COLUMNS, "model_name": "test"}
    snapshot.gpu.available = False
    try:
        result = predict_power(snapshot)
        assert result["predicted_power_w"] == 75.0
        assert result["imputed_features"] == ["gpu_utilization_pct"]
        assert result["estimate_quality"] == "reduced"
        assert "lower-confidence estimate" in result["warnings"][0]
    finally:
        model_loader.reset()


def test_live_prediction_with_valid_snapshot(monkeypatch):
    from tests.test_telemetry import make_test_snapshot
    from app.ml import model_loader
    from app.ml.predict import predict_power
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    class ConstantModel:
        def predict(self, matrix):
            return np.array([80.0])

    model_loader._model = ConstantModel()
    model_loader._pipeline = Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler())]).fit(
        pd.DataFrame([[1.0] * 9, [2.0] * 9], columns=FEATURE_COLUMNS)
    )
    model_loader._metadata = {"features": FEATURE_COLUMNS, "model_name": "test"}
    try:
        snapshot = make_test_snapshot()
        snapshot.gpu.available = True
        snapshot.gpu.utilization_pct = 10.0
        result = predict_power(snapshot)
        assert result["predicted_power_w"] == 80.0
        assert result["model_ready"] is True
    finally:
        model_loader.reset()


def test_energy_service_accumulates_two_hours_at_80_w():
    from app.services.energy_service import EnergyService

    service = EnergyService()
    service.reset()
    # The production service caps any one gap at five minutes; simulate each
    # elapsed interval explicitly while checking the 2-hour total.
    for _ in range(24):
        service.update(80.0, elapsed_s=300.0)
    assert service.get_state()["session_energy_wh"] == 160.0


def test_carbon_service_calculation_uses_provider_intensity(tmp_path):
    from app.services.carbon_service import CarbonService

    class Config:
        EMISSIONS_DIR = str(tmp_path)
        ELECTRICITY_MAPS_API_KEY = ""
        CLIMATIQ_API_KEY = ""
        CARBON_ZONE = "TEST"
        FALLBACK_CARBON_INTENSITY_G_PER_KWH = ""
        FALLBACK_CARBON_SOURCE = ""

    service = CarbonService(Config())
    service.get_intensity = lambda: {
        "carbon_intensity_g_per_kwh": 500.0,
        "source": "test fixture",
        "zone": "TEST",
        "status": "live",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    result = service.calculate_co2e(0.5)
    assert result["co2e_g"] == 250.0


def test_model_loader_rejects_missing_artifacts(tmp_path):
    from app.ml import model_loader

    class Config:
        MODEL_FILE = str(tmp_path / "missing-model.pkl")
        PREPROCESSING_FILE = str(tmp_path / "missing-preprocess.pkl")
        METADATA_FILE = str(tmp_path / "missing-metadata.json")

    model_loader.reset()
    try:
        assert model_loader.load_model(Config()) is False
        assert model_loader.is_model_ready() is False
        assert "not found" in model_loader.get_load_error()
    finally:
        model_loader.reset()


def test_model_loader_loads_matching_persisted_artifacts(tmp_path):
    import joblib
    from app.ml import model_loader
    from sklearn.linear_model import LinearRegression
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    class Config:
        MODEL_FILE = str(tmp_path / "model.pkl")
        PREPROCESSING_FILE = str(tmp_path / "preprocess.pkl")
        METADATA_FILE = str(tmp_path / "metadata.json")

    data = pd.DataFrame([[float(i + j) for j in range(9)] for i in range(4)], columns=FEATURE_COLUMNS)
    model = LinearRegression().fit(data, [10.0, 20.0, 30.0, 40.0])
    pipeline = Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler())]).fit(data)
    joblib.dump(model, Config.MODEL_FILE)
    joblib.dump(pipeline, Config.PREPROCESSING_FILE)
    with open(Config.METADATA_FILE, "w", encoding="utf-8") as metadata_file:
        json.dump({"features": FEATURE_COLUMNS, "model_name": "LinearRegression"}, metadata_file)

    model_loader.reset()
    try:
        assert model_loader.load_model(Config()) is True
        assert model_loader.is_model_ready() is True
        assert model_loader.get_metadata()["model_name"] == "LinearRegression"
    finally:
        model_loader.reset()


def test_prediction_api_returns_unavailable_prediction_without_energy_update():
    from flask import Flask
    from app.routes.predictions import predictions_bp
    from tests.test_telemetry import make_test_snapshot

    class Telemetry:
        def get_latest(self):
            return make_test_snapshot()

    class Prediction:
        def predict(self, snapshot):
            return {"predicted_power_w": None, "unavailable": True, "error": "GPU telemetry unavailable"}

    class Energy:
        def get_state(self):
            return {"session_energy_wh": 0.0}

        def update(self, power):
            raise AssertionError("Unavailable prediction must not change energy")

    app = Flask(__name__)
    app.register_blueprint(predictions_bp, url_prefix="/api")
    app.config.update(TELEMETRY_SERVICE=Telemetry(), PREDICTION_SERVICE=Prediction(), ENERGY_SERVICE=Energy())
    response = app.test_client().get("/api/prediction/current")
    assert response.status_code == 200
    result = response.get_json()
    assert result["prediction"]["predicted_power_w"] is None
    assert result["prediction"]["unavailable"] is True
    assert result["energy"]["session_energy_wh"] == 0.0


