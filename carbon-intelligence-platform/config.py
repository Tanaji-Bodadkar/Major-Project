"""
Carbon Intelligence Platform — Configuration
All runtime configuration is loaded from environment variables (.env file).
No secrets or keys are hard-coded here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-in-production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Carbon Intensity APIs
    ELECTRICITY_MAPS_API_KEY = os.environ.get("ELECTRICITY_MAPS_API_KEY", "")
    CLIMATIQ_API_KEY = os.environ.get("CLIMATIQ_API_KEY", "")

    # Grid zone for carbon intensity (Electricity Maps zone code)
    CARBON_ZONE = os.environ.get("CARBON_ZONE", "IN-WE")

    # Telemetry
    TELEMETRY_INTERVAL_S = float(os.environ.get("TELEMETRY_INTERVAL_S", "5"))

    # Static fallback carbon intensity (ONLY used if APIs fail AND this is configured)
    FALLBACK_CARBON_INTENSITY_G_PER_KWH = os.environ.get(
        "FALLBACK_CARBON_INTENSITY_G_PER_KWH", ""
    )
    FALLBACK_CARBON_SOURCE = os.environ.get(
        "FALLBACK_CARBON_SOURCE", ""
    )

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    TELEMETRY_DIR = os.path.join(DATA_DIR, "telemetry")
    MEASURED_DIR = os.path.join(DATA_DIR, "measured")
    PREDICTIONS_DIR = os.path.join(DATA_DIR, "predictions")
    EMISSIONS_DIR = os.path.join(DATA_DIR, "emissions")
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")

    # Model filenames
    MODEL_FILE = os.path.join(MODELS_DIR, "power_model.pkl")
    PREPROCESSING_FILE = os.path.join(MODELS_DIR, "preprocessing.pkl")
    METADATA_FILE = os.path.join(MODELS_DIR, "metadata.json")

    # Session storage
    SESSIONS_FILE = os.path.join(EMISSIONS_DIR, "sessions.json")

    # Maximum processes to track in telemetry
    TOP_PROCESS_COUNT = 5


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        return ProductionConfig()
    return DevelopmentConfig()

