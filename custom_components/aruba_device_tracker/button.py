"""Button platform for Aruba Device Tracker."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

from .utils import get_device_info

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ArubaIAPCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual client refresh button."""
    async_add_entities([ArubaRefreshClientsButton(entry)])


class ArubaRefreshClientsButton(ButtonEntity):
    """Immediately refresh the client list from the Aruba IAP."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_clients"
    _attr_icon = "mdi:refresh"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the refresh button."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh_clients"
        self._attr_device_info = get_device_info(entry)

    async def async_press(self) -> None:
        """Request an immediate coordinator refresh."""
        coordinator: ArubaIAPCoordinator = self._entry.runtime_data
        await coordinator.async_request_refresh()
        LOGGER.info(
            "Aruba Device Tracker: manual refresh completed; %d client(s) found",
            len(coordinator.data or {}),
        )
