"""
Unit tests for schedule.py's pure resolve_current_mode().

Loaded by file path, not by package import — `custom_components.eufy_sdk`'s own
`__init__.py` pulls in Home Assistant, which schedule.py deliberately does not need and
this test suite doesn't require installed just to exercise a pure function.
Run with: python3 -m pytest tests
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "eufy_sdk"
    / "schedule.py"
)
_spec = importlib.util.spec_from_file_location("eufy_sdk_schedule", _MODULE_PATH)
_schedule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schedule)
resolve_current_mode = _schedule.resolve_current_mode

# {raw_wire_value_as_string: label} — the same shape alarm_control_panel.py's own
# `_label_by_raw` builds from an armingMode PropertySpec's `enumValues`.
LABELS = {"0": "away", "1": "home", "2": "schedule", "3": "custom1", "63": "disarmed"}

# A live timetable captured against a real T8030 on Schedule (see eufy-sdk's own
# arming.schedule doc and mega-yfue/ha-eufy-sdk PR #67): home 07:00-20:20, custom1
# ("Night" on this account) 20:20-24:00, Thursday only (week 4).
THURSDAY_SCHEDULE = [
    {"week": 4, "start_h": 7, "start_m": 0, "end_h": 20, "end_m": 20, "mode_id": 1},
    {"week": 4, "start_h": 20, "start_m": 20, "end_h": 23, "end_m": 59, "mode_id": 3},
]


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """Build a naive local datetime — fine here, this is pure day/time arithmetic."""
    return datetime(year, month, day, hour, minute)  # noqa: DTZ001


def test_matches_the_daytime_slot() -> None:
    """2026-10-01 is a Thursday, midday falls in the Home slot."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 12, 0), LABELS)
        == "home"
    )


def test_matches_the_night_slot() -> None:
    """9pm falls in the custom1 (Night) slot."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 21, 0), LABELS)
        == "custom1"
    )


def test_start_boundary_is_inclusive() -> None:
    """The exact start minute of a slot belongs to that slot."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 7, 0), LABELS)
        == "home"
    )


def test_ordinary_end_boundary_is_exclusive() -> None:
    """20:20 belongs to the NEXT slot (custom1), not the one ending there."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 20, 20), LABELS)
        == "custom1"
    )


def test_a_slot_written_to_end_23_59_runs_to_midnight() -> None:
    """The app's own end-of-day convention: 23:59 means "to midnight"."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 23, 59), LABELS)
        == "custom1"
    )


def test_wrong_day_of_week_does_not_match() -> None:
    """2026-10-02 is a Friday — the Thursday-only schedule has nothing for it."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 2, 12, 0), LABELS) is None
    )


def test_sunday_is_eufy_week_0_not_pythons_monday_0() -> None:
    """Eufy's week field counts Sunday = 0, NOT Python's own Monday = 0 convention."""
    sunday_schedule = [
        {"week": 0, "start_h": 0, "start_m": 0, "end_h": 23, "end_m": 59, "mode_id": 0}
    ]
    # 2026-10-04 is a Sunday; 2026-10-05 is the following Monday.
    assert (
        resolve_current_mode(sunday_schedule, _dt(2026, 10, 4, 10, 0), LABELS) == "away"
    )
    assert (
        resolve_current_mode(sunday_schedule, _dt(2026, 10, 5, 10, 0), LABELS) is None
    )


def test_before_the_first_slot_and_after_the_last_is_unresolved() -> None:
    """A time no slot covers resolves to None, not a guess."""
    assert (
        resolve_current_mode(THURSDAY_SCHEDULE, _dt(2026, 10, 1, 6, 59), LABELS) is None
    )


def test_an_unmapped_mode_id_resolves_to_none() -> None:
    """A mode_id armingMode's own enum doesn't know stays unresolved, not a KeyError."""
    schedule = [
        {"week": 4, "start_h": 0, "start_m": 0, "end_h": 23, "end_m": 59, "mode_id": 99}
    ]
    assert resolve_current_mode(schedule, _dt(2026, 10, 1, 12, 0), LABELS) is None


def test_non_list_schedule_resolves_to_none() -> None:
    """Missing or malformed top-level data degrades to None rather than raising."""
    assert resolve_current_mode(None, _dt(2026, 10, 1, 12, 0), LABELS) is None
    assert resolve_current_mode("schedule", _dt(2026, 10, 1, 12, 0), LABELS) is None


def test_malformed_slots_are_skipped_not_raised() -> None:
    """One bad slot must not stop a later good slot from matching."""
    schedule = [
        "not-a-dict",
        {
            "week": 4,
            "start_h": "oops",
            "start_m": 0,
            "end_h": 23,
            "end_m": 59,
            "mode_id": 1,
        },
        {"week": 4, "end_h": 23, "end_m": 59, "mode_id": 1},  # missing start_h/start_m
        {"week": 4, "start_h": 0, "start_m": 0, "end_h": 23, "end_m": 59, "mode_id": 1},
    ]
    assert resolve_current_mode(schedule, _dt(2026, 10, 1, 12, 0), LABELS) == "home"


def test_first_matching_slot_wins_on_an_overlapping_timetable() -> None:
    """An unvalidated, overlapping timetable picks the first slot that matches."""
    overlapping = [
        {"week": 4, "start_h": 0, "start_m": 0, "end_h": 23, "end_m": 59, "mode_id": 1},
        {"week": 4, "start_h": 9, "start_m": 0, "end_h": 17, "end_m": 0, "mode_id": 3},
    ]
    assert resolve_current_mode(overlapping, _dt(2026, 10, 1, 12, 0), LABELS) == "home"
