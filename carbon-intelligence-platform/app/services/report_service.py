"""
Carbon Intelligence Platform — PDF Report Service

Generates a professional PDF session report using ReportLab.

The report explicitly states that all power, energy, and CO₂e values
are estimated using the project's telemetry-based methodology.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def generate_session_report(session: dict, reports_dir: str) -> str:
    """
    Generate a PDF report for a session.

    Args:
        session: Session dict from SessionService
        reports_dir: Directory to save the PDF

    Returns:
        Absolute path to the generated PDF file
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    except ImportError:
        raise RuntimeError(
            "ReportLab is not installed. Run: pip install reportlab"
        )

    session_id = session.get("session_id", "unknown")
    pdf_path = os.path.join(reports_dir, f"carbon_report_{session_id}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=6,
        textColor=colors.HexColor("#1a3a2a"),
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#4a7a5a"),
        spaceAfter=16,
        alignment=TA_CENTER,
    )
    heading1_style = ParagraphStyle(
        "H1Custom",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=colors.HexColor("#1a3a2a"),
        spaceBefore=12,
        spaceAfter=6,
        borderPad=4,
    )
    heading2_style = ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#2d5a3d"),
        spaceBefore=8,
        spaceAfter=4,
    )
    normal_style = styles["Normal"]
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        alignment=TA_JUSTIFY,
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#666666"),
        leading=12,
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=1,
        borderPad=6,
        backColor=colors.HexColor("#f8f8f8"),
    )
    warning_style = ParagraphStyle(
        "Warning",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#8a6000"),
        backColor=colors.HexColor("#fffbea"),
        borderColor=colors.HexColor("#ddbf00"),
        borderWidth=1,
        borderPad=6,
    )

    def make_table(data, col_widths=None):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d5a3d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f7f3")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    # ----------------------------------------------------------------
    # Build content
    # ----------------------------------------------------------------
    story = []

    # Header
    story.append(Paragraph("Carbon Intelligence Platform", title_style))
    story.append(Paragraph("Session Carbon Report", subtitle_style))
    story.append(Paragraph("Measure. Predict. Understand. Reduce.", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2d5a3d")))
    story.append(Spacer(1, 0.4 * cm))

    # Methodology disclaimer — PROMINENT
    story.append(Paragraph(
        "⚠ IMPORTANT METHODOLOGY NOTE: Power and carbon values in this report are "
        "<b>estimated</b> using a prototype machine-learning model trained on synthetic, "
        "formula-generated targets (not measured power), "
        "combined with live grid carbon intensity. These values should <b>not</b> be "
        "interpreted as direct electrical-meter measurements. They are computational "
        "estimates for awareness and decision support.",
        warning_style,
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ----------------------------------------------------------------
    # 1. Session Information
    # ----------------------------------------------------------------
    story.append(Paragraph("1. Session Information", heading1_style))

    def fmt(v, unit="", decimals=2, fallback="N/A"):
        if v is None:
            return fallback
        return f"{v:.{decimals}f} {unit}".strip()

    def fmt_duration(s):
        if s is None:
            return "N/A"
        s = int(s)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    session_data = [
        ["Field", "Value"],
        ["Session ID", session.get("session_id", "N/A")],
        ["Session Name", session.get("name", "N/A")],
        ["Start Time", session.get("start_time", "N/A")],
        ["End Time", session.get("end_time", "N/A")],
        ["Duration", fmt_duration(session.get("duration_s"))],
        ["Status", session.get("status", "N/A").upper()],
        ["Report Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")],
    ]
    story.append(make_table(session_data, col_widths=[5 * cm, 12 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    # ----------------------------------------------------------------
    # 2. Power Summary
    # ----------------------------------------------------------------
    story.append(Paragraph("2. Estimated Power Summary", heading1_style))
    story.append(Paragraph(
        "Power values are estimates produced by the ML model. "
        "They are not direct electrical measurements.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    power_data = [
        ["Metric", "Value", "Notes"],
        ["Average Estimated Power",
         fmt(session.get("average_power_w"), "W"),
         "Mean of all predictions in session"],
        ["Peak Estimated Power",
         fmt(session.get("peak_power_w"), "W"),
         "Maximum single prediction"],
    ]
    story.append(make_table(power_data, col_widths=[5.5 * cm, 4 * cm, 7.5 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    # ----------------------------------------------------------------
    # 3. Energy Summary
    # ----------------------------------------------------------------
    story.append(Paragraph("3. Estimated Energy Consumption", heading1_style))
    story.append(Paragraph(
        "Energy is calculated by integrating estimated power over time: "
        "Energy(Wh) = Σ(Power_i × Δt_i / 3600). This is an estimate.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    energy_wh = session.get("total_energy_wh")
    energy_kwh = session.get("total_energy_kwh")

    energy_data = [
        ["Metric", "Value"],
        ["Estimated Total Energy", fmt(energy_wh, "Wh", 2)],
        ["Estimated Total Energy", fmt(energy_kwh, "kWh", 4)],
        ["Duration Used", fmt_duration(session.get("duration_s"))],
    ]
    story.append(make_table(energy_data, col_widths=[7 * cm, 10 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    # ----------------------------------------------------------------
    # 4. Carbon Summary
    # ----------------------------------------------------------------
    story.append(Paragraph("4. Estimated Carbon Emissions (Scope 2)", heading1_style))
    story.append(Paragraph(
        "CO₂e = Estimated Energy (kWh) × Grid Carbon Intensity (gCO₂e/kWh). "
        "Only Scope 2 (operational electricity) emissions are calculated. "
        "Hardware manufacturing (Scope 3) is not included.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    carbon_data = [
        ["Metric", "Value"],
        ["Estimated CO₂e",
         fmt(session.get("total_co2e_g"), "gCO₂e", 2)],
        ["Estimated CO₂e",
         fmt(session.get("total_co2e_kg"), "kgCO₂e", 4)],
        ["Average Carbon Intensity",
         fmt(session.get("carbon_intensity_avg"), "gCO₂e/kWh", 1)],
        ["Carbon Data Source",
         session.get("carbon_source") or "N/A"],
    ]
    story.append(make_table(carbon_data, col_widths=[7 * cm, 10 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    # ----------------------------------------------------------------
    # 5. Figures (if available)
    # ----------------------------------------------------------------
    figures_dir = os.path.join(os.path.dirname(reports_dir), "reports", "figures")
    actual_figures_dir = os.path.join(reports_dir, "figures")

    for fig_path, caption in [
        (os.path.join(actual_figures_dir, "actual_vs_predicted.png"), "Figure 1: Synthetic Target vs Predicted Power (Prototype Training Data)"),
        (os.path.join(actual_figures_dir, "feature_importance.png"), "Figure 2: Feature Importance"),
        (os.path.join(actual_figures_dir, "model_comparison.png"), "Figure 3: Model Comparison"),
    ]:
        if os.path.isfile(fig_path):
            try:
                from reportlab.platypus import Image
                story.append(Paragraph(caption, heading2_style))
                img = Image(fig_path, width=14 * cm, height=8 * cm)
                story.append(img)
                story.append(Spacer(1, 0.3 * cm))
            except Exception as e:
                logger.warning(f"Could not include figure {fig_path}: {e}")

    # ----------------------------------------------------------------
    # 6. Methodology Note
    # ----------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("5. Methodology and Limitations", heading1_style))

    story.append(Paragraph("5.1 Power Estimation", heading2_style))
    story.append(Paragraph(
        "System power consumption is estimated using a supervised machine-learning regression "
        "model. Current artifacts were trained on synthetic, formula-generated targets, not "
        "power-meter measurements; real-world accuracy is unknown. "
        "Live telemetry (CPU utilization, frequency, RAM, disk I/O, network I/O, GPU) is "
        "collected from Windows performance counters via psutil and WMI, then passed through "
        "the same preprocessing pipeline used during training.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("5.2 Energy Calculation", heading2_style))
    story.append(Paragraph(
        "Energy is calculated using: Energy(Wh) = Σ[Power_i(W) × Δt_i(s) / 3600], "
        "where Power_i is the predicted power at each sampling interval and Δt_i is the "
        "elapsed time since the previous sample. This is then converted to kWh by dividing by 1000.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("5.3 Carbon Intensity", heading2_style))
    story.append(Paragraph(
        "Grid carbon intensity is fetched from the Electricity Maps API (primary) or "
        "Climatiq API (secondary). These APIs provide real-time gCO₂e/kWh values for "
        "specific grid zones. CO₂e is calculated as: CO₂e(gCO₂e) = Energy(kWh) × Intensity(gCO₂e/kWh).",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("5.4 Scope", heading2_style))
    story.append(Paragraph(
        "This report covers Scope 2 operational emissions only — indirect emissions from "
        "purchased electricity. It does not include Scope 3 (hardware manufacturing, "
        "logistics, end-of-life) emissions.",
        body_style,
    ))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("5.5 Limitations", heading2_style))
    limitations = [
        "Power estimates are derived from a model trained on specific hardware configurations. Accuracy varies by hardware.",
        "The model estimates total system power; process-level attribution is not supported.",
        "Live prediction is unavailable when required GPU utilization telemetry is unavailable.",
        "Full-session CO₂e is withheld if any integrated energy interval had no carbon intensity.",
        "Carbon intensity is fetched at ~15-minute intervals; intra-interval variation is not captured.",
        "This system measures operational electricity only; it does not measure hardware manufacturing carbon.",
    ]
    for lim in limitations:
        story.append(Paragraph(f"• {lim}", body_style))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "This report was generated by the Carbon Intelligence Platform. "
        "All estimates are provided for awareness and decision support. "
        "Do not use these values as certified emissions data.",
        disclaimer_style,
    ))

    # ----------------------------------------------------------------
    # Build PDF
    # ----------------------------------------------------------------
    doc.build(story)
    logger.info(f"PDF report generated: {pdf_path}")
    return pdf_path

