"""
Carbon Intelligence Platform — Telemetry API Routes

GET /api/telemetry/current  — Live telemetry snapshot
"""

from flask import Blueprint, jsonify, current_app

telemetry_bp = Blueprint("telemetry_api", __name__)


@telemetry_bp.route("/telemetry/current")
def get_current_telemetry():
    """
    Return the most recently collected telemetry snapshot as JSON.
    If no snapshot is available yet, collect one immediately.
    """
    telemetry_service = current_app.config.get("TELEMETRY_SERVICE")
    if telemetry_service is None:
        return jsonify({"error": "Telemetry service not initialized."}), 503

    snapshot = telemetry_service.get_latest()
    if snapshot is None:
        # First request — collect immediately
        try:
            snapshot = telemetry_service.collect_once()
        except Exception as e:
            return jsonify({"error": f"Failed to collect telemetry: {str(e)}"}), 503

    return jsonify(snapshot.to_dict())


@telemetry_bp.route("/telemetry/status")
def get_telemetry_status():
    """Return telemetry service status."""
    telemetry_service = current_app.config.get("TELEMETRY_SERVICE")
    if telemetry_service is None:
        return jsonify({"status": "not_initialized"}), 503

    snapshot = telemetry_service.get_latest()
    return jsonify({
        "status": "running" if snapshot else "initializing",
        "provider": "WindowsTelemetryProvider",
        "interval_s": telemetry_service.interval_s,
        "has_data": snapshot is not None,
        "gpu_available": snapshot.gpu.available if snapshot else None,
        "gpu_unavailability_reason": (
            snapshot.gpu.unavailability_reason
            if snapshot and not snapshot.gpu.available
            else None
        ),
    })

