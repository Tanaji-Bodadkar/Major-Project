"""
Carbon Intelligence Platform — Dashboard Routes

Serves the HTML page templates.
All data is fetched by the frontend via the JSON API endpoints.
"""

from flask import Blueprint, render_template, current_app

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    return render_template("dashboard.html")


@dashboard_bp.route("/analytics")
def analytics():
    return render_template("analytics.html")


@dashboard_bp.route("/workflow")
def workflow():
    return render_template("workflow.html")


@dashboard_bp.route("/recommendations")
def recommendations():
    return render_template("recommendations.html")


@dashboard_bp.route("/sessions")
def sessions():
    return render_template("sessions.html")


@dashboard_bp.route("/report-view/<session_id>")
def report_view(session_id):
    return render_template("report.html", session_id=session_id)

