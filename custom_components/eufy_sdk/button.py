"""Button platform — device-level actions the bridge exposes (HomeBase reboot)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory

from .entity import EufySdkDeviceEntity, has_capability

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EufySdkDataUpdateCoordinator
    from .data import EufySdkConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: EufySdkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create Reboot / Refresh-Last-Event / Resume-Schedule buttons."""
    coordinator = entry.runtime_data.coordinator
    entities: list[ButtonEntity] = [
        EufySdkRebootButton(coordinator, sn)
        for sn, dev in coordinator.data.items()
        if dev.get("canReboot")
    ]
    # A "Refresh Last Event" button per camera/doorbell (same set as the event Image
    # entity, gated on `stream`): forces the bridge to pull the newest event cover now —
    # a manual override for when the auto-refresh raced the HomeBase writing the crop.
    entities.extend(
        EufyRefreshEventButton(coordinator, sn)
        for sn, dev in coordinator.data.items()
        if dev.get("stream")
    )
    # One "Resume Schedule" button per station with a guard mode — the counterpart to
    # the alarm panel's Away/Home/Night/Disarm buttons for the one settable mode HA's
    # alarm_control_panel domain has no button for at all. See EufyResumeScheduleButton.
    entities.extend(
        EufyResumeScheduleButton(coordinator, sn)
        for sn, dev in coordinator.data.items()
        if has_capability(dev, "arming")
    )
    async_add_entities(entities)


class EufySdkRebootButton(EufySdkDeviceEntity, ButtonEntity):
    """Reboot a HomeBase — a device-level action, not a writable property."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Reboot"

    def __init__(self, coordinator: EufySdkDataUpdateCoordinator, sn: str) -> None:
        """Bind to a HomeBase serial."""
        super().__init__(coordinator, sn)
        self._attr_unique_id = f"{sn}_reboot"

    async def async_press(self) -> None:
        """Reboot the HomeBase (it drops offline for a minute or two)."""
        client = self.coordinator.config_entry.runtime_data.client
        await client.reboot(self._sn)


class EufyRefreshEventButton(EufySdkDeviceEntity, ButtonEntity):
    """Force a 'Last event' image refresh — pull the newest event cover now."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:image-refresh"
    _attr_name = "Refresh Last Event"

    def __init__(self, coordinator: EufySdkDataUpdateCoordinator, sn: str) -> None:
        """Bind to a camera/doorbell serial."""
        super().__init__(coordinator, sn)
        self._attr_unique_id = f"{sn}_refresh_last_event"

    async def async_press(self) -> None:
        """Ask the bridge to re-pull the newest event cover (nudges the Image)."""
        client = self.coordinator.config_entry.runtime_data.client
        await client.refresh_event_image(self._sn)


class EufyResumeScheduleButton(EufySdkDeviceEntity, ButtonEntity):
    """
    Resume the Eufy app's own time-based guard-mode schedule.

    HA's `alarm_control_panel` domain has no "schedule" state or action at all — only
    Away/Home/Night/Disarm — so this is a plain button rather than something the panel
    itself could expose. It exists specifically to rebuild a "resume the schedule after
    a manual override" automation (e.g. "if armed Home via the Home app, resume
    schedule shortly after" — a real workflow confirmed working against this account on
    a prior integration): a trigger on the alarm panel's `armed_home` state, calling
    this button's `press` as the action.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Resume Schedule"

    def __init__(self, coordinator: EufySdkDataUpdateCoordinator, sn: str) -> None:
        """Bind to a station serial."""
        super().__init__(coordinator, sn)
        self._attr_unique_id = f"{sn}_resume_schedule"

    async def async_press(self) -> None:
        """Set the station's guard mode back to `schedule`."""
        client = self.coordinator.config_entry.runtime_data.client
        await client.set_property(self._sn, "armingMode", "schedule")
