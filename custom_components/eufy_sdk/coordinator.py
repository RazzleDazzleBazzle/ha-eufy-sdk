"""DataUpdateCoordinator for eufy_sdk — owns the bridge connection + the device list."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EufySdkApiClientAuthenticationError, EufySdkApiClientError

if TYPE_CHECKING:
    from .data import EufySdkConfigEntry


class EufySdkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Keep the bridge connected and expose the device list as `{sn: device}`."""

    config_entry: EufySdkConfigEntry

    # Anker Solix devices (separate account/backend), kept apart from the eufy `data`
    # so the eufy platforms never iterate them: `{sn: {productCode, name, category,
    # capabilities, values, ...}}`. Empty unless the bridge has SOLIX_* configured;
    # reassigned per-update, so the class-level {} is only an initial fallback. Live
    # values arrive via `solixReading` events.
    solix_devices: ClassVar[dict[str, dict]] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init the coordinator, plus the event-only state a poll never carries."""
        super().__init__(*args, **kwargs)
        # station sn -> the last armingModeChanged push's own resolved `currentMode`
        # label. NOT part of the polled device list (armingMode reads back the
        # POLICY, e.g. literally "schedule" forever) — this is the schedule/geo
        # resolution that only ever arrives on this one event, so it has to be
        # cached here rather than re-derived from a fresh read. See
        # alarm_control_panel.py.
        self.current_arming_modes: dict[str, str] = {}

    async def _async_update_data(self) -> dict[str, dict]:
        """Ensure the connection is up, confirm we're authed, and return the devices."""
        client = self.config_entry.runtime_data.client
        try:
            if not client.connected:
                await client.connect()
            auth = await client.auth_status()
            state = auth.get("state")
            if state in ("require_2fa", "require_captcha"):
                # Genuinely needs the user — start the reauth flow.
                msg = f"bridge needs re-authentication (state: {state})"
                raise ConfigEntryAuthFailed(msg)
            if state != "ok":
                # Transient: the bridge is still booting/logging in ("pending" after a
                # restart). Retry next interval instead of freezing the entry in reauth;
                # one boot-window poll must not stop updates indefinitely.
                msg = f"bridge not ready yet (state: {state})"
                raise UpdateFailed(msg)
            devices = await client.list_devices()
        except EufySdkApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except EufySdkApiClientError as err:
            raise UpdateFailed(err) from err
        # Solix is optional + independent: a hiccup must not fail the eufy update.
        try:
            solix = await client.list_solix_devices()
            self.solix_devices = {d["sn"]: d for d in solix if d.get("sn")}
        except EufySdkApiClientError:
            self.solix_devices = getattr(self, "solix_devices", {})
        return {d["sn"]: d for d in devices if d.get("sn")}
