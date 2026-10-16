"""
Carbon Intelligence Platform — Application Entry Point

Run with:
    python app.py

Or in production:
    flask run --host=0.0.0.0 --port=5000
"""

import os
import sys
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config import get_config

logger = logging.getLogger(__name__)


def main():
    cfg = get_config()
    flask_app = create_app(cfg)

    # ----------------------------------------------------------------
    # Initialize services as singletons attached to app config
    # ----------------------------------------------------------------
    from app.services.telemetry_service import TelemetryService
    from app.services.prediction_service import PredictionService
    from app.services.energy_service import EnergyService
    from app.services.carbon_service import CarbonService
    from app.services.session_service import SessionService
    from app.services.analytics_service import AnalyticsService

    session_service = SessionService(cfg)
    telemetry_service = TelemetryService(cfg, session_service=session_service)
    prediction_service = PredictionService(cfg)
    energy_service = EnergyService()
    carbon_service = CarbonService(cfg)
    analytics_service = AnalyticsService(cfg)

    # Attach to Flask app config so routes can access them
    flask_app.config["TELEMETRY_SERVICE"] = telemetry_service
    flask_app.config["PREDICTION_SERVICE"] = prediction_service
    flask_app.config["ENERGY_SERVICE"] = energy_service
    flask_app.config["CARBON_SERVICE"] = carbon_service
    flask_app.config["SESSION_SERVICE"] = session_service
    flask_app.config["ANALYTICS_SERVICE"] = analytics_service

    # Start background telemetry collection
    telemetry_service.start()

    logger.info("=" * 60)
    logger.info("  Carbon Intelligence Platform")
    logger.info("  Measure. Predict. Understand. Reduce.")
    logger.info("=" * 60)
    logger.info(f"  Dashboard: http://127.0.0.1:5000")
    logger.info(f"  Telemetry interval: {cfg.TELEMETRY_INTERVAL_S}s")
    logger.info(f"  Carbon zone: {cfg.CARBON_ZONE}")

    model_path = cfg.MODEL_FILE
    if os.path.isfile(model_path):
        logger.info(f"  ML model: found ({model_path})")
    else:
        logger.warning(
            f"  ML model NOT found. Run 'python -m app.ml.train' to train it."
        )
    logger.info("=" * 60)

    try:
        flask_app.run(
            host="127.0.0.1",
            port=5000,
            debug=cfg.DEBUG,
            use_reloader=False,  # Prevent double-start of telemetry thread
        )
    finally:
        logger.info("Shutting down telemetry service...")
        telemetry_service.stop()


if __name__ == "__main__":
    main()

