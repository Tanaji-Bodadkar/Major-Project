"""
Carbon Intelligence Platform — Emissions, Sessions, Analytics & Recommendations API

GET  /api/carbon/current         — Live carbon intensity and CO₂e
GET  /api/session/current        — Active session summary
GET  /api/sessions               — All completed sessions
POST /api/session/start          — Start a monitoring session
POST /api/session/stop           — Stop the active session
GET  /api/analytics              — Analytics data for charts
GET  /api/recommendations        — Current recommendations
"""

from flask import Blueprint, jsonify, request, current_app

emissions_bp = Blueprint("emissions_api", __name__)


@emissions_bp.route("/carbon/current")
def get_current_carbon():
    """Return live carbon intensity and cumulative CO₂e for current session."""
    carbon_service = current_app.config.get("CARBON_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")

    if not carbon_service:
        return jsonify({"error": "Carbon service not initialized."}), 503

    intensity_data = carbon_service.get_intensity()
    co2e_data = carbon_service.get_session_emissions()

    return jsonify({
        "intensity": intensity_data,
        "co2e": co2e_data,
    })


@emissions_bp.route("/session/current")
def get_current_session():
    """Return the active session state."""
    session_service = current_app.config.get("SESSION_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")
    carbon_service = current_app.config.get("CARBON_SERVICE")

    if not session_service:
        return jsonify({"error": "Session service not initialized."}), 503

    active = session_service.get_active_session()
    if not active:
        return jsonify({"session_active": False, "session": None})

    energy_state = energy_service.get_state() if energy_service else {}
    intensity_data = carbon_service.get_latest_intensity() if carbon_service else {}
    co2e_result = carbon_service.get_session_emissions() if carbon_service else {}
    co2e_g = co2e_result.get("co2e_g")

    return jsonify({
        "session_active": True,
        "session": {
            **active,
            "current_energy_wh": energy_state.get("session_energy_wh"),
            "current_energy_kwh": energy_state.get("session_energy_kwh"),
            "current_co2e_g": co2e_g,
            "current_power_w": energy_state.get("current_power_w"),
            "peak_power_w": energy_state.get("peak_power_w"),
            "average_power_w": energy_state.get("average_power_w"),
            "duration_s": energy_state.get("session_duration_s"),
            "carbon_intensity": intensity_data.get("carbon_intensity_g_per_kwh") if intensity_data else None,
            "carbon_source": intensity_data.get("source") if intensity_data else None,
            "carbon_intensity_timestamp": intensity_data.get("timestamp") if intensity_data else None,
            "carbon_coverage_status": co2e_result.get("status"),
            "uncovered_energy_wh": co2e_result.get("uncovered_energy_wh", 0.0),
        }
    })


@emissions_bp.route("/sessions")
def get_all_sessions():
    """Return all completed sessions."""
    session_service = current_app.config.get("SESSION_SERVICE")
    if not session_service:
        return jsonify({"error": "Session service not initialized."}), 503
    sessions = session_service.get_all_sessions()
    return jsonify({"sessions": sessions, "count": len(sessions)})


@emissions_bp.route("/session/start", methods=["POST"])
def start_session():
    """Start a new monitoring session."""
    session_service = current_app.config.get("SESSION_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")

    if not session_service:
        return jsonify({"error": "Session service not initialized."}), 503

    if session_service.is_session_active():
        return jsonify({
            "error": "A session is already active. Stop it first.",
            "session": session_service.get_active_session(),
        }), 409

    data = request.get_json() or {}
    name = data.get("name")

    # Reset energy accumulator
    if energy_service:
        energy_service.reset()
    carbon_service = current_app.config.get("CARBON_SERVICE")
    if carbon_service:
        carbon_service.reset_session_emissions()

    session = session_service.start_session(name=name)
    return jsonify({"session": session, "status": "started"}), 201


@emissions_bp.route("/session/stop", methods=["POST"])
def stop_session():
    """Stop the active monitoring session."""
    session_service = current_app.config.get("SESSION_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")
    carbon_service = current_app.config.get("CARBON_SERVICE")

    if not session_service:
        return jsonify({"error": "Session service not initialized."}), 503

    if not session_service.is_session_active():
        return jsonify({"error": "No active session."}), 404

    energy_state = energy_service.get_state() if energy_service else {}
    co2e_data = carbon_service.get_session_emissions() if carbon_service else {}
    intensity_g = None
    source = None
    intensity_timestamp = None
    if carbon_service:
        intensity_info = carbon_service.get_latest_intensity() or {}
        intensity_g = intensity_info.get("carbon_intensity_g_per_kwh")
        source = intensity_info.get("source")
        intensity_timestamp = intensity_info.get("timestamp")

    completed = session_service.stop_session(
        energy_state=energy_state,
        co2e_data=co2e_data,
        carbon_intensity=intensity_g,
        carbon_source=source,
        carbon_intensity_timestamp=intensity_timestamp,
    )

    return jsonify({"session": completed, "status": "stopped"})


@emissions_bp.route("/analytics")
def get_analytics():
    """Return analytics data for dashboard charts."""
    analytics_service = current_app.config.get("ANALYTICS_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")
    session_service = current_app.config.get("SESSION_SERVICE")

    if not analytics_service:
        return jsonify({"error": "Analytics service not initialized."}), 503

    window = int(request.args.get("window_minutes", 10))

    power_trend = analytics_service.get_recent_power_trend(window_minutes=window)
    telemetry_trend = analytics_service.get_recent_telemetry_trend(window_minutes=window)

    comparison = None
    if energy_service and session_service and session_service.is_session_active():
        energy_state = energy_service.get_state()
        comparison = analytics_service.compare_with_previous_session(
            current_energy_kwh=energy_state.get("session_energy_kwh", 0),
            current_duration_s=energy_state.get("session_duration_s", 0),
        )

    return jsonify({
        "power_trend": power_trend,
        "telemetry_trend": telemetry_trend,
        "session_comparison": comparison,
    })


@emissions_bp.route("/recommendations")
def get_recommendations():
    """Return current recommendations based on system state."""
    from app.services.recommendation_service import generate_recommendations

    telemetry_service = current_app.config.get("TELEMETRY_SERVICE")
    energy_service = current_app.config.get("ENERGY_SERVICE")
    carbon_service = current_app.config.get("CARBON_SERVICE")
    session_service = current_app.config.get("SESSION_SERVICE")
    analytics_service = current_app.config.get("ANALYTICS_SERVICE")

    snapshot = telemetry_service.get_latest() if telemetry_service else None
    energy_state = energy_service.get_state() if energy_service else {}
    carbon_data = carbon_service.get_latest_intensity() or {} if carbon_service else {}
    session_active = session_service.is_session_active() if session_service else False
    cpu_history = session_service.get_cpu_history() if session_service else []

    comparison = None
    if analytics_service and energy_service and session_active:
        energy_s = energy_service.get_state()
        comparison = analytics_service.compare_with_previous_session(
            current_energy_kwh=energy_s.get("session_energy_kwh", 0),
            current_duration_s=energy_s.get("session_duration_s", 0),
        )

    recs = generate_recommendations(
        telemetry_snapshot=snapshot,
        energy_state=energy_state,
        carbon_data=carbon_data,
        session_comparison=comparison,
        cpu_history=cpu_history,
        session_active=session_active,
    )

    return jsonify({"recommendations": recs, "count": len(recs)})

