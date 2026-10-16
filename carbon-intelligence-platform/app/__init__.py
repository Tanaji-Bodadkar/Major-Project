"""
Carbon Intelligence Platform — Flask Application Factory
"""

import os
import logging
from flask import Flask
from config import get_config

logger = logging.getLogger(__name__)


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load configuration
    cfg = config or get_config()
    app.config.from_object(cfg)

    # Ensure required data directories exist
    _ensure_directories(cfg)

    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.telemetry import telemetry_bp
    from app.routes.predictions import predictions_bp
    from app.routes.emissions import emissions_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(telemetry_bp, url_prefix="/api")
    app.register_blueprint(predictions_bp, url_prefix="/api")
    app.register_blueprint(emissions_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if cfg.DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Carbon Intelligence Platform starting up.")
    logger.info(f"Carbon zone: {cfg.CARBON_ZONE}")
    logger.info(
        f"Electricity Maps API: {'configured' if cfg.ELECTRICITY_MAPS_API_KEY else 'NOT configured'}"
    )
    logger.info(
        f"Climatiq API: {'configured' if cfg.CLIMATIQ_API_KEY else 'NOT configured'}"
    )

    return app


def _ensure_directories(cfg):
    """Create required data directories if they don't exist."""
    dirs = [
        cfg.TELEMETRY_DIR,
        cfg.MEASURED_DIR,
        cfg.PREDICTIONS_DIR,
        cfg.EMISSIONS_DIR,
        cfg.MODELS_DIR,
        cfg.REPORTS_DIR,
        os.path.join(cfg.REPORTS_DIR, "figures"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

