"""
Carbon Intelligence Platform — Recommendation Engine

Rule-based, evidence-driven decision support.
All recommendations include a reason and the evidence that triggered them.

Important design constraints:
- Does NOT claim process-level power attribution
- Does NOT recommend stopping required workloads
- Critical workloads receive awareness, not interruption requests
- Recommendations only trigger when data genuinely supports them
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Thresholds — configurable
HIGH_CPU_THRESHOLD = 75.0          # % CPU for "high-impact workload"
SUSTAINED_HIGH_CPU_READINGS = 6    # N consecutive readings above threshold
HIGH_BACKGROUND_THRESHOLD = 30.0  # % CPU when user says no main workload running
HIGH_CARBON_INTENSITY = 500.0     # gCO2e/kWh considered "elevated"
ENERGY_COMPARISON_THRESHOLD = 15.0  # % above previous session to flag


def generate_recommendations(
    telemetry_snapshot,
    energy_state: dict,
    carbon_data: dict,
    session_comparison: Optional[dict],
    cpu_history: list,  # list of recent cpu_utilization_pct values
    session_active: bool,
) -> list:
    """
    Generate context-aware recommendations based on current system state.

    Args:
        telemetry_snapshot: Current TelemetrySnapshot
        energy_state: dict from EnergyService.get_state()
        carbon_data: dict from CarbonService.get_intensity()
        session_comparison: dict from AnalyticsService.compare_with_previous_session() or None
        cpu_history: list of recent CPU % readings (newest last)
        session_active: whether a session is currently running

    Returns:
        list of recommendation dicts, each with:
          - id: unique identifier
          - category: category string
          - severity: 'info' | 'warning' | 'critical'
          - icon: emoji icon for UI
          - title: short title
          - body: explanation with evidence
          - action: optional suggested action (never mandatory)
    """
    recommendations = []

    if not session_active or telemetry_snapshot is None:
        return recommendations

    cpu_pct = telemetry_snapshot.cpu.utilization_pct
    ram_pct = telemetry_snapshot.memory.utilization_pct
    current_power = energy_state.get("current_power_w")
    avg_power = energy_state.get("average_power_w", 0)
    intensity = carbon_data.get("carbon_intensity_g_per_kwh")

    # ----------------------------------------------------------------
    # Category 1: High-impact workload detection
    # ----------------------------------------------------------------
    sustained_high = (
        len(cpu_history) >= SUSTAINED_HIGH_CPU_READINGS
        and all(c >= HIGH_CPU_THRESHOLD for c in cpu_history[-SUSTAINED_HIGH_CPU_READINGS:])
    )

    if sustained_high:
        recommendations.append({
            "id": "high_impact_workload",
            "category": "workload",
            "severity": "warning",
            "icon": "⚠",
            "title": "High-impact workload detected",
            "body": (
                f"CPU utilization has remained above {HIGH_CPU_THRESHOLD:.0f}% "
                f"for the last {SUSTAINED_HIGH_CPU_READINGS} readings "
                f"(current: {cpu_pct:.1f}%). "
                f"{'Estimated power: ' + str(round(current_power, 1)) + ' W. ' if current_power else ''}"
                f"This may indicate an active compute-intensive workload."
            ),
            "action": (
                "If the workload is required (e.g. ML training, rendering, compilation), "
                "no action is needed. The platform will track and quantify the impact."
            ),
        })

    # ----------------------------------------------------------------
    # Category 2: Background activity detection
    # (High CPU but no user-declared main workload — heuristic only)
    # ----------------------------------------------------------------
    top_processes = telemetry_snapshot.top_processes
    if top_processes and not sustained_high and cpu_pct > HIGH_BACKGROUND_THRESHOLD:
        top = top_processes[0]
        known_background = any(
            bg in top.name.lower()
            for bg in [
                "antimalware", "mrt", "trustedinstaller", "wuauclt",
                "searchindexer", "onedrive", "dropbox", "backup",
            ]
        )
        if known_background:
            recommendations.append({
                "id": "background_activity",
                "category": "background",
                "severity": "info",
                "icon": "💡",
                "title": "Background activity detected",
                "body": (
                    f"A process commonly associated with background activity is contributing to system activity "
                    f"(overall CPU: {cpu_pct:.1f}%, "
                    f"top process: {top.name} at {top.cpu_pct:.1f}%). "
                    f"Background activity increases resource consumption."
                ),
                "action": (
                    "Review the process and its purpose before taking action. Do not stop required or managed software."
                ),
                "evidence": {
                    "cpu_utilization_pct": round(cpu_pct, 1),
                    "process_name": top.name,
                    "process_cpu_pct": round(top.cpu_pct, 1),
                },
                "limitations": "Process name is a heuristic; it does not establish that activity is unnecessary.",
            })

    # ----------------------------------------------------------------
    # Category 3: Carbon-aware scheduling
    # ----------------------------------------------------------------
    if intensity is not None and intensity > HIGH_CARBON_INTENSITY:
        recommendations.append({
            "id": "carbon_aware_scheduling",
            "category": "carbon",
            "severity": "info",
            "icon": "ℹ",
            "title": "Carbon intensity is currently elevated",
            "body": (
                f"The current grid carbon intensity is {intensity:.0f} gCO₂e/kWh "
                f"(threshold: {HIGH_CARBON_INTENSITY:.0f} gCO₂e/kWh). "
                f"Running compute-intensive tasks now generates more carbon than "
                f"during lower-intensity periods."
            ),
            "action": (
                "If the workload deadline allows, consider deferring it to a period "
                "of lower carbon intensity. This is optional and should not compromise "
                "required computation."
            ),
        })

    # ----------------------------------------------------------------
    # Category 4: Historical comparison
    # ----------------------------------------------------------------
    if session_comparison is not None:
        pct_diff = session_comparison.get("percentage_difference", 0)
        if pct_diff >= ENERGY_COMPARISON_THRESHOLD:
            recommendations.append({
                "id": "historical_comparison",
                "category": "comparison",
                "severity": "info",
                "icon": "📊",
                "title": "Energy consumption above previous session",
                "body": session_comparison["note"],
                "action": (
                    "Review the current workload profile and compare with the "
                    "previous session in the Sessions page to identify differences."
                ),
            })
        elif pct_diff <= -ENERGY_COMPARISON_THRESHOLD:
            recommendations.append({
                "id": "historical_comparison_positive",
                "category": "comparison",
                "severity": "info",
                "icon": "✅",
                "title": "Energy consumption below previous session",
                "body": session_comparison["note"],
                "action": None,
            })

    # ----------------------------------------------------------------
    # Category 5: Carbon intensity unavailable
    # ----------------------------------------------------------------
    intensity_status = carbon_data.get("status")
    if intensity_status in ("error", "unavailable"):
        recommendations.append({
            "id": "carbon_unavailable",
            "category": "system",
            "severity": "info",
            "icon": "⚡",
            "title": "Carbon intensity data unavailable",
            "body": (
                "Live carbon intensity could not be retrieved. "
                "CO₂e estimates are not available for this period. "
                f"Reason: {carbon_data.get('error', 'Unknown')}"
            ),
            "action": "Check your API key configuration in .env file.",
        })

    return recommendations

