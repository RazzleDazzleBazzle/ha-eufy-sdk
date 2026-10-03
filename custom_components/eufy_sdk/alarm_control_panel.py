"""
Alarm control panel platform — a station's `armingMode` as a native HA security panel.

The bridge already exposes guard/arming mode as a plain writable enum property
(`armingMode`, capability `arming`, station-codec devices only) — the same generic
mechanism every other writable enum rides as a `select` (see select.py). This platform
gives it the native `alarm_control_panel` domain instead, so it gets HA's own
Lovelace panel card, voice-assistant "arm/disarm" phrasing, and (via HA's own HomeKit
bridge) a proper HomeKit Security System accessory — none of which target a `select`.

away/home/custom1/disarmed are wire-confirmed as SETTABLE (see the SDK's arming
capability) even though the station can REPORT five more (schedule/custom2-3/off/geo).
Reading `armingMode` while the policy is schedule/geo answers that literal policy name
forever, not what the schedule has actually resolved to right now — a station cycling
Home/Night on a schedule would otherwise report nothing but "schedule" indefinitely.
For those two specifically, `alarm_state` falls back, in order:

1. The coordinator's `current_arming_modes` cache, populated from the armingModeChanged
   push's own resolved `currentMode` field (see `__init__.py`'s `_on_event` +
   coordinator.py) — freshest when one has arrived, but only ever updates on that one
   event, never a poll. A push missed entirely (e.g. a reconnect landing mid-transition)
   leaves this showing whatever the PREVIOUS transition set, indefinitely.
2. The station's own `schedule` property (eufy-sdk's `arming.schedule`, see
   schedule.py's `resolve_current_mode`) — the day/time timetable the station itself
   consults, reported on every regular poll rather than only a push, so it fills
   exactly the gap (1) leaves whenever the exact transition push was missed.

custom2/custom3/off have no fallback at all (no observed real-world meaning to fall back
to, and no schedule slot ever reports those ids) and stay STATE_UNKNOWN.

`custom1` -> Arm Night specifically is an ACCOUNT-SPECIFIC choice, not a general one:
it matches this account's own Eufy app schedule, which has custom1 configured as its
Night period (confirmed against the actual schedule, mirroring the prior integration's
own documented reasoning for the same mapping) — not something the wire reports or the
SDK asserts. Update `_ARM_NIGHT_MODE` below if that schedule slot is ever reconfigured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.util import dt as dt_util

from .entity import EufySdkPropertyEntity, has_capability
from .schedule import resolve_current_mode

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EufySdkDataUpdateCoordinator
    from .data import EufySdkConfigEntry

# The property this platform owns — excluded from the generic select platform
# (see select.py) so a station gets one alarm panel, not a panel plus a redundant
# raw select for the same value.
ARMING_PROP = "armingMode"
ARMING_OWNED_PROPS = frozenset({ARMING_PROP})

# Eufy guard-mode label for Arm Night — see module docstring: account-specific, not a
# general "custom1 means night" assumption.
_ARM_NIGHT_MODE = "custom1"

# Wire-confirmed settable modes only (the labels `armingMode`'s enumValues use for
# their own keys are the same strings `device.set` accepts back).
_STATE_BY_LABEL: dict[str, AlarmControlPanelState] = {
    "away": AlarmControlPanelState.ARMED_AWAY,
    "home": AlarmControlPanelState.ARMED_HOME,
    "disarmed": AlarmControlPanelState.DISARMED,
    _ARM_NIGHT_MODE: AlarmControlPanelState.ARMED_NIGHT,
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: EufySdkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one alarm panel per station that reports a writable `armingMode`."""
    coordinator = entry.runtime_data.coordinator
    entities = []
    for sn, dev in coordinator.data.items():
        if not has_capability(dev, "arming"):
            continue
        spec = next(
            (
                s
                for s in entry.runtime_data.properties.get(sn, [])
                if s["name"] == ARMING_PROP and s.get("writable")
            ),
            None,
        )
        if spec is not None:
            entities.append(EufySdkAlarmControlPanel(coordinator, sn, spec))
    async_add_entities(entities)


class EufySdkAlarmControlPanel(EufySdkPropertyEntity, AlarmControlPanelEntity):
    """A station's guard mode as a HA alarm control panel."""

    _attr_name = None  # the panel IS the device (the station)
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    # The bridge sits behind your own network/HA auth already; a second PIN here would
    # just be friction. Revisit if this ever needs to satisfy Alexa/Google Guard Mode's
    # own code requirements.
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: EufySdkDataUpdateCoordinator,
        sn: str,
        spec: dict[str, Any],
    ) -> None:
        """Bind to the station's `armingMode` spec and build the raw->label map."""
        super().__init__(coordinator, sn, spec)
        # enumValues is {raw: label}; JSON object keys arrive as strings.
        self._label_by_raw = {str(k): str(v) for k, v in spec["enumValues"].items()}

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Fallback order: direct map, then currentMode, then the schedule."""
        v = self.prop_value
        if v is None:
            return None
        label = self._label_by_raw.get(str(v))
        state = _STATE_BY_LABEL.get(label)
        if state is not None:
            return state
        # armingMode read back the POLICY (schedule/geo/off/custom2/custom3), not a
        # directly mappable state. Prefer the last armingModeChanged push's own resolved
        # value — freshest when one has arrived — but that only ever updates on that one
        # event, never a poll (see coordinator.py's current_arming_modes), so a push
        # missed entirely (e.g. a reconnect landing mid-transition) leaves it stuck on
        # whatever the PREVIOUS transition set. The station's own schedule timetable
        # (reported on every regular poll) fills exactly that gap — see schedule.py.
        resolved = self.coordinator.current_arming_modes.get(self._sn)
        if resolved is None:
            resolved = resolve_current_mode(
                self.device.get("state", {}).get("schedule"),
                dt_util.now(),
                self._label_by_raw,
            )
        return _STATE_BY_LABEL.get(resolved)

    async def async_alarm_disarm(self, code: str | None = None) -> None:  # noqa: ARG002
        """Disarm."""
        await self.write("disarmed")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:  # noqa: ARG002
        """Arm Home."""
        await self.write("home")

    async def async_alarm_arm_away(self, code: str | None = None) -> None:  # noqa: ARG002
        """Arm Away."""
        await self.write("away")

    async def async_alarm_arm_night(self, code: str | None = None) -> None:  # noqa: ARG002
        """Arm Night — see the module docstring for why this targets custom1."""
        await self.write(_ARM_NIGHT_MODE)
