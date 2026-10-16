"""Convert an HWiNFO sensor log into the project's canonical power-reading CSV.

The importer supports CPU Package Power and Total System Power. These are
hardware/firmware sensor readings, not external wall-socket measurements.
"""

import argparse
import logging
import os
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)


def _find_column(columns, explicit, token):
    if explicit:
        if explicit not in columns:
            raise ValueError(f"Column {explicit!r} was not found in the HWiNFO CSV")
        return explicit
    candidates = [column for column in columns if token in str(column).casefold()]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one HWiNFO column containing {token!r}; found {candidates}. "
            "Use the matching --power-column argument if the log has multiple sensor columns."
        )
    return candidates[0]


def _timestamps(frame: pd.DataFrame, timezone_name: str, timestamp_column=None,
                date_column=None, time_column=None) -> pd.Series:
    if timestamp_column:
        if timestamp_column not in frame:
            raise ValueError(f"Timestamp column {timestamp_column!r} was not found")
        raw = frame[timestamp_column]
    else:
        date_column = _find_column(frame.columns, date_column, "date")
        time_column = _find_column(frame.columns, time_column, "time")
        raw = frame[date_column].astype(str).str.strip() + " " + frame[time_column].astype(str).str.strip()

    parsed = pd.to_datetime(raw, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"HWiNFO log contains {int(parsed.isna().sum())} invalid timestamp(s)")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone {timezone_name!r}") from exc

    if parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(zone, ambiguous="raise", nonexistent="raise")
    else:
        parsed = parsed.dt.tz_convert(zone)
    return parsed.dt.tz_convert("UTC")


def convert_hwinfo_log(
    frame: pd.DataFrame,
    session_id: str,
    workload_label: str,
    timezone_name: str = "Asia/Kolkata",
    power_column: str | None = None,
    timestamp_column: str | None = None,
    date_column: str | None = None,
    time_column: str | None = None,
    target_sensor: str = "cpu-package-power",
) -> pd.DataFrame:
    """Return canonical readings compatible with ``measured_dataset``."""
    if not session_id.strip():
        raise ValueError("A Carbon Intelligence app session ID is required")
    if not workload_label.strip():
        raise ValueError("A workload label is required (for example, cpu_load)")
    if frame.empty:
        raise ValueError("HWiNFO CSV contains no sensor samples")

    if target_sensor == "cpu-package-power":
        sensor_token = "cpu package power"
        scope = "cpu_package_power_hwinfo"
        scope_note = "HWiNFO CPU Package Power sensor; CPU-domain power, not whole-laptop or wall-input power"
    elif target_sensor == "total-system-power":
        sensor_token = "total system power"
        scope = "platform_reported_power_hwinfo"
        scope_note = "HWiNFO Total System Power platform sensor; hardware-reported estimate, not wall-input meter power"
    else:
        raise ValueError("target_sensor must be cpu-package-power or total-system-power")
    power_column = _find_column(frame.columns, power_column, sensor_token)
    timestamps = _timestamps(
        frame, timezone_name, timestamp_column, date_column, time_column
    )
    power = pd.to_numeric(frame[power_column], errors="coerce")
    valid = power.notna() & np.isfinite(power.to_numpy(dtype=float)) & (power >= 0)
    result = pd.DataFrame({
        "timestamp": timestamps[valid].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "power_w": power[valid].astype(float).to_numpy(),
        "session_id": session_id.strip(),
        "workload_label": workload_label.strip(),
        "measurement_scope": scope,
        "notes": scope_note,
    })
    result = result.sort_values("timestamp").reset_index(drop=True)
    if result.empty:
        raise ValueError(f"No valid numeric samples found in {power_column!r}")
    if result["timestamp"].duplicated().any():
        raise ValueError(
            "HWiNFO log has duplicate timestamps at its recorded precision. "
            "Increase logging timestamp precision or remove duplicate samples before import."
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert HWiNFO power sensor CSV into canonical project readings."
    )
    parser.add_argument("--input", required=True, help="Raw HWiNFO sensor CSV")
    parser.add_argument("--output", required=True, help="Canonical readings CSV output")
    parser.add_argument("--session-id", required=True, help="Matching Carbon Intelligence session ID")
    parser.add_argument("--workload", required=True, help="Workload label, e.g. idle or cpu_load")
    parser.add_argument(
        "--target-sensor", choices=["cpu-package-power", "total-system-power"],
        default="cpu-package-power",
        help="HWiNFO sensor to import; Total System Power may be absent on some systems",
    )
    parser.add_argument("--timezone", default="Asia/Kolkata", help="Timezone for HWiNFO local timestamps")
    parser.add_argument("--power-column", help="Exact selected sensor column name if auto-detection is ambiguous")
    parser.add_argument("--timestamp-column", help="Combined timestamp column, if present")
    parser.add_argument("--date-column", help="Date column name; auto-detected by default")
    parser.add_argument("--time-column", help="Time column name; auto-detected by default")
    args = parser.parse_args()

    frame = pd.read_csv(args.input, encoding="utf-8-sig")
    readings = convert_hwinfo_log(
        frame,
        args.session_id,
        args.workload,
        timezone_name=args.timezone,
        power_column=args.power_column,
        timestamp_column=args.timestamp_column,
        date_column=args.date_column,
        time_column=args.time_column,
        target_sensor=args.target_sensor,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    readings.to_csv(args.output, index=False)
    logger.info("Imported %d HWiNFO power samples to %s", len(readings), args.output)
    logger.info("Sensor scope: %s", readings["measurement_scope"].iloc[0])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()

