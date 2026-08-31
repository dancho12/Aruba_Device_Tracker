"""Diagnostic client sensors for Aruba Device Tracker."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, UnitOfDataRate
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import CONF_TRACKED_DEVICES, DOMAIN

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ArubaIAPCoordinator


def _link_speed(value: Any) -> int | float | None:
    """Extract an Mbps value from Aruba values such as '1200(good)' or '130M'."""
    if value is None or not (match := re.search(r"\d+(?:\.\d+)?", str(value))):
        return None
    parsed = float(match.group())
    return int(parsed) if parsed.is_integer() else parsed


def _identity(value: Any) -> Any:
    """Return an Aruba diagnostic value unchanged."""
    return value


@dataclass(frozen=True, kw_only=True)
class ArubaClientSensorDescription(SensorEntityDescription):
    """Describe a disabled-by-default client diagnostic sensor."""

    value_fn: Callable[[Any], Any] = _identity


SENSOR_DESCRIPTIONS: tuple[ArubaClientSensorDescription, ...] = (
    ArubaClientSensorDescription(
        key="ip",
        translation_key="ip_address",
        icon="mdi:ip-network-outline",
    ),
    ArubaClientSensorDescription(
        key="ipv6",
        translation_key="ipv6_address",
        icon="mdi:ip-network-outline",
    ),
    ArubaClientSensorDescription(
        key="os",
        translation_key="operating_system",
        icon="mdi:laptop",
    ),
    ArubaClientSensorDescription(
        key="essid",
        translation_key="essid",
        icon="mdi:wifi-cog",
    ),
    ArubaClientSensorDescription(
        key="access_point",
        translation_key="access_point",
        icon="mdi:access-point",
    ),
    ArubaClientSensorDescription(
        key="channel",
        translation_key="channel",
        icon="mdi:access-point-network",
    ),
    ArubaClientSensorDescription(
        key="type",
        translation_key="client_type",
        icon="mdi:wifi-star",
    ),
    ArubaClientSensorDescription(
        key="role",
        translation_key="role",
        icon="mdi:account-key-outline",
    ),
    ArubaClientSensorDescription(
        key="signal",
        translation_key="signal",
        icon="mdi:wifi",
    ),
    ArubaClientSensorDescription(
        key="speed",
        translation_key="link_speed",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_fn=_link_speed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up disabled diagnostic sensors for every selected client."""
    coordinator: ArubaIAPCoordinator = entry.runtime_data
    configured = entry.options.get(
        CONF_TRACKED_DEVICES,
        entry.data.get(CONF_TRACKED_DEVICES),
    )
    selected = (
        {format_mac(mac) for mac in configured}
        if configured is not None
        else {
            *map(format_mac, coordinator.last_seen),
            *map(format_mac, (coordinator.data or {})),
        }
    )

    async_add_entities(
        ArubaClientSensor(coordinator, mac, description)
        for mac in sorted(selected)
        for description in SENSOR_DESCRIPTIONS
    )


class ArubaClientSensor(SensorEntity):
    """A diagnostic value reported for one Aruba client."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False

    entity_description: ArubaClientSensorDescription

    def __init__(
        self,
        coordinator: ArubaIAPCoordinator,
        mac: str,
        description: ArubaClientSensorDescription,
    ) -> None:
        """Initialise a client diagnostic sensor."""
        self._coordinator = coordinator
        self._mac = format_mac(mac)
        self.entity_description = description
        self._attr_unique_id = f"{self._mac}_{description.key}"
        client = (coordinator.data or {}).get(self._mac, {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=client.get("name") or self._mac,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe an enabled sensor to coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write the latest diagnostic value."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether this client is present in the latest successful poll."""
        return bool(
            self._coordinator.last_update_success
            and self._mac in (self._coordinator.data or {})
        )

    @property
    def native_value(self) -> Any:
        """Return the latest Aruba value."""
        data = (self._coordinator.data or {}).get(self._mac, {})
        return self.entity_description.value_fn(data.get(self.entity_description.key))
