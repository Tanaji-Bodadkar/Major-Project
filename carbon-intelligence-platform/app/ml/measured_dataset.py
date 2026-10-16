"""Align timestamped power readings with the app's session-tagged telemetry."""

import argparse
import logging
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.ml.preprocessing import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

REQUIRED_METER_COLUMNS = {"timestamp", "power_w", "session_id"}


def _parse_timestamps(frame: pd.DataFrame, source: str) -> pd.Series:
    def parse_aware(value):
        stamp = pd.Timestamp(value)
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise ValueError(f"{source} timestamps must include a UTC offset (for example, Z or +05:30)")
        return stamp.tz_convert("UTC")

    parsed = frame["timestamp"].map(parse_aware)
    if parsed.isna().any():
        bad_count = int(parsed.isna().sum())
        raise ValueError(f"{source} has {bad_count} invalid timestamp(s)")
    return parsed


def align_meter_readings(
    telemetry: pd.DataFrame,
    meter: pd.DataFrame,
    tolerance_s: float = 2.5,
) -> tuple[pd.DataFrame, dict]:
    """Nearest-time join readings within each power-reading session, without crossing sessions."""
    missing_meter = sorted(REQUIRED_METER_COLUMNS - set(meter.columns))
    if missing_meter:
        raise ValueError(f"Power readings CSV missing required columns: {missing_meter}")
    missing_features = [name for name in FEATURE_COLUMNS if name not in telemetry.columns]
    if missing_features:
        raise ValueError(f"Telemetry CSV missing model features: {missing_features}")
    if tolerance_s <= 0:
        raise ValueError("Timestamp tolerance must be greater than zero")
    if meter.empty or telemetry.empty:
        raise ValueError("Power readings and telemetry must both contain rows")

    telemetry = telemetry.copy()
    meter = meter.copy()
    telemetry["_telemetry_timestamp"] = _parse_timestamps(telemetry, "Telemetry CSV")
    meter["_meter_timestamp"] = _parse_timestamps(meter, "Power readings CSV")
    meter["power_w"] = pd.to_numeric(meter["power_w"], errors="coerce")
    if meter["power_w"].isna().any() or not np.isfinite(meter["power_w"].to_numpy()).all():
        raise ValueError("Meter power_w contains missing or non-finite values")
    if (meter["power_w"] < 0).any():
        raise ValueError("Meter power_w cannot be negative")
    if meter["session_id"].isna().any() or (meter["session_id"].astype(str).str.strip() == "").any():
        raise ValueError("Every meter reading needs a session_id")
    if meter.duplicated(["session_id", "_meter_timestamp"]).any():
        raise ValueError("Meter CSV contains duplicate timestamps within a session")

    for feature in FEATURE_COLUMNS:
        telemetry[feature] = pd.to_numeric(telemetry[feature], errors="coerce")
    telemetry = telemetry.sort_values("_telemetry_timestamp")
    telemetry_has_session_ids = "session_id" in telemetry.columns
    if telemetry_has_session_ids:
        telemetry["session_id"] = telemetry["session_id"].fillna("").astype(str)
    matches = []
    tolerance = pd.Timedelta(seconds=float(tolerance_s))
    for session_id, session_meter in meter.groupby("session_id", sort=False):
        session_meter = session_meter.sort_values("_meter_timestamp")
        session_meter_id = str(session_id)
        if telemetry_has_session_ids:
            session_telemetry = telemetry[telemetry["session_id"] == session_meter_id]
        else:
            # Legacy telemetry lacks IDs; constrain it to this meter session's time span.
            start, end = session_meter["_meter_timestamp"].min(), session_meter["_meter_timestamp"].max()
            session_telemetry = telemetry[
                telemetry["_telemetry_timestamp"].between(start, end, inclusive="both")
            ]
        joined = pd.merge_asof(
            session_meter,
            session_telemetry[["_telemetry_timestamp", *FEATURE_COLUMNS]].sort_values("_telemetry_timestamp"),
            left_on="_meter_timestamp",
            right_on="_telemetry_timestamp",
            direction="nearest",
            tolerance=tolerance,
        )
        joined["session_id"] = session_meter_id
        joined["meter_match_offset_seconds"] = (
            joined["_telemetry_timestamp"] - joined["_meter_timestamp"]
        ).abs().dt.total_seconds().to_numpy()
        matches.append(joined)

    combined = pd.concat(matches, ignore_index=True)
    matched = combined["_telemetry_timestamp"].notna()
    result = combined.loc[matched].copy()
    result["timestamp"] = result["_meter_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    result = result.drop(columns=["_meter_timestamp", "_telemetry_timestamp"])
    # Retain only provenance fields that actually exist in the meter export.
    output_columns = [
        "timestamp", "session_id", "workload_label", "hardware_id", "meter_model",
        "measurement_scope", "notes", "meter_match_offset_seconds", *FEATURE_COLUMNS, "power_w",
    ]
    output_columns = [c for c in output_columns if c in result.columns]
    result = result[output_columns].rename(columns={"power_w": "measured_power_w"})

    report = {
        "meter_rows": int(len(combined)),
        "matched_rows": int(len(result)),
        "unmatched_rows": int((~matched).sum()),
        "session_count": int(meter["session_id"].nunique()),
        "tolerance_seconds": float(tolerance_s),
    }
    if result.empty:
        raise ValueError("No meter rows matched telemetry within the selected time tolerance")
    return result, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Join exported power readings (meter or HWiNFO) to app telemetry by nearest timestamp."
    )
    parser.add_argument("--telemetry", required=True, help="App telemetry CSV export")
    parser.add_argument(
        "--meter", "--power-readings", dest="meter", required=True,
        help="Power readings CSV with timestamp, power_w, session_id",
    )
    parser.add_argument("--output", default="data/processed/measured_training_data.csv")
    parser.add_argument("--tolerance-seconds", type=float, default=2.5)
    args = parser.parse_args()

    telemetry = pd.read_csv(args.telemetry)
    meter = pd.read_csv(args.meter)
    aligned, report = align_meter_readings(telemetry, meter, args.tolerance_seconds)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    aligned.to_csv(args.output, index=False)
    logger.info("Matched power-reading dataset saved: %s", args.output)
    logger.info("Alignment summary: %s", report)
    if report["unmatched_rows"]:
        logger.warning(
            "%d power readings did not match telemetry and were excluded. Check clocks, timestamps, and tolerance.",
            report["unmatched_rows"],
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()

