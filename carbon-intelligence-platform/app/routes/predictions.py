"""
Carbon Intelligence Platform — Prediction & Energy API Routes

GET /api/prediction/current  — Latest ML power prediction
GET /api/energy/current      — Current session energy state
GET /api/model/status        — ML model loading status
POST /api/what-if            — What-if analysis
"""

from flask import Blueprint, jsonify, request, current_app

predictions_bp = Blueprint("predictions_api", __name__)


@predictions_bp.route("/prediction/current")
def get_current_prediction():
    """
    Return the latest ML-generated power prediction.
    Collects fresh telemetry and runs the model.
    """
    telemetry_service = current_app.config.get("TELEMETRY_SERVICE")
    prediction_service = current_app.config.get("PREDICTION_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")
    session_service = current_app.config.get("SESSION_SERVICE")
    carbon_service = current_app.config.get("CARBON_SERVICE")

    if not all([telemetry_service, prediction_service, energy_service]):
        return jsonify({"error": "Services not initialized."}), 503

    snapshot = telemetry_service.get_latest()
    if snapshot is None:
        return jsonify({
            "predicted_power_w": None,
            "model_ready": False,
            "error": "No telemetry available yet.",
        })

    prediction = prediction_service.predict(snapshot)

    session_active = session_service.is_session_active() if session_service else False
    if session_active and prediction.get("predicted_power_w") is not None:
        energy_state = energy_service.update(
            prediction["predicted_power_w"], timestamp=snapshot.timestamp
        )
        if energy_state.get("last_sample_accepted"):
            session_service.update_cpu_history(snapshot.cpu.utilization_pct)
            increment_wh = energy_state.get("last_energy_increment_wh", 0.0)
            if increment_wh > 0 and carbon_service:
                intensity = carbon_service.get_intensity()
                carbon_service.record_energy_interval(increment_wh, intensity)
                carbon_service.save_emission_record({
                    "session_id": (session_service.get_active_session() or {}).get("session_id"),
                    "timestamp": snapshot.timestamp,
                    "energy_increment_wh": increment_wh,
                    "carbon_intensity_g_per_kwh": intensity.get("carbon_intensity_g_per_kwh"),
                    "carbon_source": intensity.get("source"),
                    "carbon_intensity_timestamp": intensity.get("timestamp"),
                    "status": intensity.get("status"),
                })
    elif session_active and prediction.get("predicted_power_w") is None:
        energy_service.break_series(snapshot.timestamp)
        energy_state = energy_service.get_state()
    else:
        energy_state = energy_service.get_state()

    return jsonify({
        "prediction": prediction,
        "energy": energy_state,
    })


@predictions_bp.route("/energy/current")
def get_current_energy():
    """Return current energy accumulation state."""
    energy_service = current_app.config.get("ENERGY_SERVICE")
    if energy_service is None:
        return jsonify({"error": "Energy service not initialized."}), 503
    return jsonify(energy_service.get_state())


@predictions_bp.route("/model/status")
def get_model_status():
    """Return ML model loading status and metadata."""
    prediction_service = current_app.config.get("PREDICTION_SERVICE")
    if prediction_service is None:
        return jsonify({"error": "Prediction service not initialized."}), 503
    return jsonify(prediction_service.get_model_status())


@predictions_bp.route("/what-if", methods=["POST"])
def what_if():
    """
    Calculate projected additional energy and CO₂e.

    Expected JSON body:
    {
        "power_w": 72.4,
        "additional_hours": 2.0,
        "carbon_intensity_g_per_kwh": 520.0
    }
    """
    from app.services.whatif_service import calculate_what_if

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required."}), 400

    try:
        power_w = float(data.get("power_w", 0))
        additional_hours = float(data.get("additional_hours", 0))
        carbon_intensity = float(data.get("carbon_intensity_g_per_kwh", 0))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    try:
        result = calculate_what_if(power_w, additional_hours, carbon_intensity)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)

