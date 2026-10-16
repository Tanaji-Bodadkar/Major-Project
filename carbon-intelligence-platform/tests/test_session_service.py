"""
Unit tests for session management logic.
"""

import sys
import os
import json
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockConfig:
    """Minimal config for testing sessions."""
    def __init__(self, tmp_dir):
        self.SESSIONS_FILE = os.path.join(tmp_dir, "sessions.json")
        self.EMISSIONS_DIR = tmp_dir


def test_start_session():
    with tempfile.TemporaryDirectory() as tmp:
        from app.services.session_service import SessionService
        svc = SessionService(MockConfig(tmp))
        session = svc.start_session(name="Test Session")
        assert session["status"] == "active"
        assert session["name"] == "Test Session"
        assert session["session_id"] is not None
        assert svc.is_session_active() is True


def test_stop_session_persists():
    with tempfile.TemporaryDirectory() as tmp:
        from app.services.session_service import SessionService
        svc = SessionService(MockConfig(tmp))
        svc.start_session()
        energy_state = {
            "average_power_w": 72.4,
            "peak_power_w": 95.0,
            "session_energy_wh": 0.36,
            "session_energy_kwh": 0.00036,
            "session_duration_s": 18.0,
        }
        co2e_data = {"co2e_g": 0.187, "co2e_kg": 0.000187}
        completed = svc.stop_session(energy_state, co2e_data)
        assert completed["status"] == "completed"
        assert completed["average_power_w"] == 72.4
        assert svc.is_session_active() is False

        # Verify saved to JSON
        sessions = svc.get_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == completed["session_id"]


def test_double_start_returns_existing():
    """Starting a session when one is active should return existing session."""
    with tempfile.TemporaryDirectory() as tmp:
        from app.services.session_service import SessionService
        svc = SessionService(MockConfig(tmp))
        s1 = svc.start_session(name="First")
        s2 = svc.start_session(name="Second")  # Should return first
        assert s1["session_id"] == s2["session_id"]


def test_no_active_session_on_start():
    with tempfile.TemporaryDirectory() as tmp:
        from app.services.session_service import SessionService
        svc = SessionService(MockConfig(tmp))
        assert svc.is_session_active() is False
        assert svc.get_active_session() is None


def test_cpu_history_tracking():
    with tempfile.TemporaryDirectory() as tmp:
        from app.services.session_service import SessionService
        svc = SessionService(MockConfig(tmp))
        for v in [30.0, 45.0, 78.0, 82.0, 90.0]:
            svc.update_cpu_history(v)
        history = svc.get_cpu_history()
        assert len(history) == 5
        assert history[-1] == 90.0

