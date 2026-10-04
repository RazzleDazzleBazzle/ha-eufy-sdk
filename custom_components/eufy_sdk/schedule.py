"""
Resolve a station's Schedule/Geo-enforced mode from its own timetable.

`armingMode` reads back only the literal policy name ("schedule"/"geo") for as long as
that policy is active — never the mode it's actually enforcing. The only other source is
the station's own `schedule` property (eufy-sdk's `arming.schedule`, wire param 1254): a
day/time timetable delivered on every regular poll, not just a push, that the station
itself consults to decide which mode applies right now. See `alarm_control_panel.py` for
how this combines with the (fresher, when it exists) `armingModeChanged` push's own
resolved value.

Kept free of Home Assistant imports so it's trivially unit-testable (see
tests/test_schedule.py) — a caller passes in whatever "now" and raw values it has.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# A slot's end time written exactly 23:59 means "runs to midnight", not "stops at the
# 23:59 mark" — confirmed against a live capture (a station cycling to its custom1/Night
# slot at the top of its PREVIOUS slot's end time, not one minute before it). There's no
# way to write 24:00 in an h:m field, so the app uses this as its own end-of-day
# convention. Every other boundary is ordinarily exclusive (see `resolve_current_mode`'s
# own doc).
_END_OF_DAY = (23, 59)
_MINUTES_PER_DAY = 24 * 60


def resolve_current_mode(
    schedule: Any,
    now: datetime,
    label_by_raw: dict[str, str],
) -> str | None:
    """
    Which mode's slot in `schedule` covers `now`, or None if nothing usable matched.

    `schedule` is `arming.schedule`'s raw value. CONFIRMED LIVE (2026-10-04) this is an
    OBJECT, not a bare array: `{account_id, schedules: [...]}`, the slot array one key
    deep — this function accepts that shape (unwrapping `schedules`) and, defensively, a
    bare list too, in case a different account/firmware ever reports one directly. Each
    slot is `{week, start_h, start_m, end_h, end_m, mode_id}`, `week` 0 = Sunday (NOT
    Python's own `datetime.weekday()` convention, which is Monday = 0 — converted
    internally). A slot's end boundary is EXCLUSIVE, except a slot written to end
    exactly 23:59, which runs to midnight (see `_END_OF_DAY`).

    Getting the wrapper shape wrong is exactly how this went unnoticed before: a caller
    built against a bare-array assumption gets nothing usable back, silently, from every
    single call — which is precisely what happened here from the day this shipped until
    a live "mode shows Off instead of Home" report traced it back to this property.

    `label_by_raw` is the same `{raw_wire_value_as_string: label}` map an armingMode
    PropertySpec's own `enumValues` already provides (see `alarm_control_panel.py`'s
    `_label_by_raw`) — `mode_id` is documented as the identical wire integer, so no
    separate mapping is needed.

    Malformed input (not a list/dict, a non-dict entry, a missing/non-numeric field, an
    unmapped `mode_id`) is skipped rather than raising: a caller showing "unknown" for
    one bad slot is far better than a crashed coordinator update over a property this
    SDK doesn't independently wire-confirm.
    """
    if isinstance(schedule, dict):
        schedule = schedule.get("schedules")
    if not isinstance(schedule, list):
        return None
    eufy_week = (now.weekday() + 1) % 7
    minutes_now = now.hour * 60 + now.minute
    for slot in schedule:
        if not isinstance(slot, dict):
            continue
        try:
            week = int(slot["week"])
            start = int(slot["start_h"]) * 60 + int(slot["start_m"])
            end_h, end_m = int(slot["end_h"]), int(slot["end_m"])
            mode_id = int(slot["mode_id"])
        except (KeyError, TypeError, ValueError):
            continue
        end = _MINUTES_PER_DAY if (end_h, end_m) == _END_OF_DAY else end_h * 60 + end_m
        if week == eufy_week and start <= minutes_now < end:
            return label_by_raw.get(str(mode_id))
    return None
