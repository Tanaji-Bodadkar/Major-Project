"""
Carbon Intelligence Platform — Telemetry Service

Manages the telemetry provider and CSV storage.
Maintains the latest snapshot for API access.
"""

import os
import csv
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.telemetry.base import TelemetrySnapshot
from app.telemetry.windows import WindowsTelemetryProvider

logger = logging.getLogger(__name__)

# CSV header — matches TelemetrySnapshot.to_csv_row() keys
CSV_COLUMNS = [
    "timestamp", "collection_interval_s",
    "cpu_utilization_pct", "cpu_frequency_mhz",
    "cpu_user_pct", "cpu_privileged_pct", "cpu_idle_pct", "cpu_logical_count",
    "ram_total_mb", "ram_available_mb", "ram_used_mb", "ram_utilization_pct",
    "disk_read_mb_s", "disk_write_mb_s",
    "network_sent_mb_s", "network_recv_mb_s",
    "gpu_available", "gpu_utilization_pct", "gpu_memory_used_mb",
    "process_count", "top_process_name", "top_process_cpu_pct", "top_process_memory_mb",
]

MEASURED_CSV_COLUMNS = ["session_id", *CSV_COLUMNS]


class TelemetryService:
    """
    Manages telemetry collection, storage, and state.

    Usage:
        service = TelemetryService(config)
        service.start()         # begins background collection
        snapshot = service.get_latest()
        service.stop()
    """

    def __init__(self, config, session_service=None):
        self.config = config
        self.interval_s = config.TELEMETRY_INTERVAL_S
        self.telemetry_dir = config.TELEMETRY_DIR
        data_dir = getattr(config, "DATA_DIR", os.path.dirname(self.telemetry_dir))
        self.measured_dir = getattr(config, "MEASURED_DIR", os.path.join(data_dir, "measured"))
        self.session_service = session_service
        self.top_process_count = config.TOP_PROCESS_COUNT

        self._provider = WindowsTelemetryProvider(
            interval_s=self.interval_s,
            top_process_count=self.top_process_count,
        )
        self._latest_snapshot: Optional[TelemetrySnapshot] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Prime the disk/network delta counters with a baseline reading
        self._prime_collectors()

    def _prime_collectors(self):
        """
        Take one snapshot to initialize delta-based counters (disk/network).
        The first real snapshot after this will have valid rate measurements.
        """
        try:
            logger.info("Priming telemetry collectors (initializing delta counters)...")
            self._provider.get_snapshot()
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Priming failed (non-fatal): {e}")

    def start(self):
        """Start background telemetry collection thread."""
        if self._running:
            logger.warning("TelemetryService already running.")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._collection_loop,
            name="TelemetryCollector",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"TelemetryService started (interval={self.interval_s}s).")

    def stop(self):
        """Stop background collection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("TelemetryService stopped.")

    def get_latest(self) -> Optional[TelemetrySnapshot]:
        """Return the most recently collected snapshot (thread-safe)."""
        with self._lock:
            return self._latest_snapshot

    def collect_once(self) -> TelemetrySnapshot:
        """
        Collect a single snapshot immediately (blocking).
        Also updates the internal latest snapshot.
        """
        snapshot = self._provider.get_snapshot()
        with self._lock:
            self._latest_snapshot = snapshot
        self._save_to_csv(snapshot)
        return snapshot

    def _collection_loop(self):
        """Background thread: collect telemetry every interval_s seconds."""
        logger.info("Telemetry collection loop started.")
        while self._running:
            try:
                snapshot = self._provider.get_snapshot()
                with self._lock:
                    self._latest_snapshot = snapshot
                self._save_to_csv(snapshot)
            except Exception as e:
                logger.error(f"Telemetry collection error: {e}")
            time.sleep(self.interval_s)
        logger.info("Telemetry collection loop stopped.")

    def _save_to_csv(self, snapshot: TelemetrySnapshot):
        """Append snapshot to daily CSV file."""
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            csv_path = os.path.join(
                self.telemetry_dir, f"telemetry_{date_str}.csv"
            )

            row = snapshot.to_csv_row()
            file_exists = os.path.isfile(csv_path)

            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)

            active_session = (
                self.session_service.get_active_session()
                if self.session_service is not None else None
            )
            if active_session:
                self._save_measured_sample(snapshot, active_session["session_id"], date_str)

        except Exception as e:
            logger.error(f"Error saving telemetry to CSV: {e}")

    def _save_measured_sample(self, snapshot: TelemetrySnapshot, session_id: str, date_str: str):
        """Save telemetry with its exact app session ID for external meter alignment."""
        try:
            os.makedirs(self.measured_dir, exist_ok=True)
            path = os.path.join(self.measured_dir, f"telemetry_{date_str}.csv")
            exists = os.path.isfile(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=MEASURED_CSV_COLUMNS)
                if not exists:
                    writer.writeheader()
                writer.writerow({"session_id": session_id, **snapshot.to_csv_row()})
        except Exception as e:
            logger.error("Error saving session-tagged telemetry: %s", e)

