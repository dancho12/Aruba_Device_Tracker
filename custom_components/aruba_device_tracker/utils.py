"""Shared utilities for Aruba Device Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return shared DeviceInfo for the IAP control device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Aruba IAP ({entry.data.get('host', '')})",
        manufacturer="Aruba Networks (HPE)",
        model="Instant AP",
    )
