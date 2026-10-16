"""
Carbon Intelligence Platform — Report Generation Route

GET /api/report/<session_id>  — Download PDF report for a session
"""

import os
from flask import Blueprint, send_file, jsonify, current_app

reports_bp = Blueprint("reports_api", __name__)


@reports_bp.route("/report/<session_id>")
def download_report(session_id):
    """Generate and return a PDF report for the specified session."""
    from app.services.report_service import generate_session_report

    session_service = current_app.config.get("SESSION_SERVICE")
    if not session_service:
        return jsonify({"error": "Session service not initialized."}), 503

    session = session_service.get_session_by_id(session_id)
    if not session:
        return jsonify({"error": f"Session '{session_id}' not found."}), 404

    try:
        reports_dir = current_app.config["REPORTS_DIR"]
        pdf_path = generate_session_report(session, reports_dir)
        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"carbon_report_{session_id}.pdf",
        )
    except Exception as e:
        return jsonify({"error": f"Report generation failed: {str(e)}"}), 500

