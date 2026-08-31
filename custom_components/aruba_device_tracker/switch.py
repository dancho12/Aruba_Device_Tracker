"""Switch platform — Aruba Device Tracker toggles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import (
    CONF_CLEANUP_ENABLED,
    DEFAULT_CLEANUP_ENABLED,
)
from .utils import get_device_info

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for the IAP control device."""
    async_add_entities([ArubaCleanupSwitch(entry)])


# ---------------------------------------------------------------------------
# Cleanup-enabled switch (new)
# ---------------------------------------------------------------------------


class ArubaCleanupSwitch(SwitchEntity):
    """
    Toggle automatic removal of stale device tracker entities.

    When ON, devices that have not been seen for the configured number of
    days (set via the 'Cleanup After Days' number entity) will have their
    tracker entity and entity registry entry removed automatically.

    Defaults to OFF so no data is deleted without explicit opt-in.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the cleanup-enabled switch."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_cleanup_enabled"
        self._attr_name = "Auto-Remove Stale Devices"
        self._attr_device_info = get_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return whether stale-device cleanup is active."""
        return self._entry.options.get(
            CONF_CLEANUP_ENABLED,
            self._entry.data.get(CONF_CLEANUP_ENABLED, DEFAULT_CLEANUP_ENABLED),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Enable automatic stale-device cleanup."""
        await self._set(value=True)

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Disable automatic stale-device cleanup."""
        await self._set(value=False)

    async def _set(self, *, value: bool) -> None:
        """Persist the cleanup preference to options."""
        new_options = {**self._entry.options, CONF_CLEANUP_ENABLED: value}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()
        LOGGER.debug("Aruba Device Tracker: auto-remove stale devices set to %s", value)
