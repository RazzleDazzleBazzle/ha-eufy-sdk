"""Select platform — one select per writable enum property."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .alarm_control_panel import ARMING_OWNED_PROPS
from .entity import EufySdkPropertyEntity, classify

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
    """Create a select for every writable enum property that lists its options."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        EufySdkSelect(coordinator, sn, spec)
        for sn in coordinator.data
        for spec in entry.runtime_data.properties.get(sn, [])
        # The alarm_control_panel platform owns armingMode — don't also surface it as
        # a raw select (would double the control, and let you "select" an unsettable
        # mode like schedule/off/geo that silently no-ops on write).
        if spec["name"] not in ARMING_OWNED_PROPS and classify(spec) == "select"
    )


class EufySdkSelect(EufySdkPropertyEntity, SelectEntity):
    """A writable enum property as a select — options are the enum labels."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: EufySdkDataUpdateCoordinator,
        sn: str,
        spec: dict[str, Any],
    ) -> None:
        """Build the raw<->label maps from the spec's enumValues."""
        super().__init__(coordinator, sn, spec)
        # enumValues is {raw: label}; JSON object keys arrive as strings.
        self._label_by_raw = {str(k): str(v) for k, v in spec["enumValues"].items()}
        self._raw_by_label = {v: k for k, v in self._label_by_raw.items()}
        self._attr_options = list(self._label_by_raw.values())

    @property
    def current_option(self) -> str | None:
        """The label for the property's current raw value."""
        v = self.prop_value
        return None if v is None else self._label_by_raw.get(str(v))

    async def async_select_option(self, option: str) -> None:
        """Write the raw value behind the chosen label."""
        raw = self._raw_by_label.get(option)
        if raw is None:
            return
        # Send an int when the raw code is numeric, else the raw string.
        value: int | str = int(raw) if raw.lstrip("-").isdigit() else raw
        await self.write(value)
