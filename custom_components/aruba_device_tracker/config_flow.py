"""Config flow for Aruba Device Tracker."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .aruba_client import ArubaIAPClient
from .const import (
    CONF_CLEANUP_DAYS,
    CONF_CLEANUP_ENABLED,
    CONF_SCAN_INTERVAL,
    CONF_TRACKED_DEVICES,
    DEFAULT_CLEANUP_DAYS,
    DEFAULT_CLEANUP_ENABLED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CLEANUP_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_CLEANUP_DAYS,
    MIN_SCAN_INTERVAL,
)

LOGGER = logging.getLogger(__name__)


def _device_select_options(
    devices: dict[str, dict[str, Any]],
    stored_names: dict[str, str] | None = None,
) -> list[SelectOptionDict]:
    """Build friendly, stable options for the device multi-select."""
    stored_names = stored_names or {}
    options = []
    for mac in sorted(devices):
        normalised_mac = format_mac(mac)
        name = devices[mac].get("name") or stored_names.get(normalised_mac)
        label = f"{name} ({normalised_mac})" if name else normalised_mac
        options.append(SelectOptionDict(value=normalised_mac, label=label))
    return options


def _device_selector(options: list[SelectOptionDict]) -> SelectSelector:
    """Return the native HA multi-select used for tracked clients."""
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


async def _test_connection(
    hass: HomeAssistant,
    host: str,
    username: str,
    password: str,
) -> tuple[str | None, dict[str, dict[str, Any]]]:
    """Test connectivity and return an error key plus discovered clients."""
    client = ArubaIAPClient(host=host, username=username, password=password)
    try:
        logged_in = await hass.async_add_executor_job(client.login)
        if not logged_in:
            return "invalid_auth", {}
        clients = await hass.async_add_executor_job(client.get_clients)
        await hass.async_add_executor_job(client.logout)
        if clients is None:
            return "api_access_denied", {}
    except Exception:
        LOGGER.debug("Aruba IAP connection test exception", exc_info=True)
        return "cannot_connect", {}
    else:
        return None, clients


class ArubaIAPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aruba Device Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user step — connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            error_key, clients = await _test_connection(
                self.hass, host, username, password
            )
            if error_key:
                errors["base"] = error_key
            else:
                self._connection_data = {
                    CONF_HOST: host,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                }
                self._discovered_clients = clients
                return await self.async_step_tracking()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle step 2 — tracking and polling preferences."""
        if user_input is not None:
            self._tracking_data = {
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                CONF_CLEANUP_ENABLED: user_input[CONF_CLEANUP_ENABLED],
                CONF_CLEANUP_DAYS: user_input[CONF_CLEANUP_DAYS],
            }
            return await self.async_step_devices()

        return self.async_show_form(
            step_id="tracking",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(
                        int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    ),
                    vol.Optional(
                        CONF_CLEANUP_ENABLED, default=DEFAULT_CLEANUP_ENABLED
                    ): bool,
                    vol.Optional(
                        CONF_CLEANUP_DAYS, default=DEFAULT_CLEANUP_DAYS
                    ): vol.All(
                        int, vol.Range(min=MIN_CLEANUP_DAYS, max=MAX_CLEANUP_DAYS)
                    ),
                }
            ),
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user explicitly choose which discovered clients to expose."""
        if user_input is not None:
            tracked_devices = sorted(
                format_mac(mac) for mac in user_input.get(CONF_TRACKED_DEVICES, [])
            )
            data = {
                **self._connection_data,
                **self._tracking_data,
                CONF_TRACKED_DEVICES: tracked_devices,
            }
            return self.async_create_entry(
                title=f"Aruba IAP ({self._connection_data[CONF_HOST]})",
                data=data,
            )

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TRACKED_DEVICES, default=[]): _device_selector(
                        _device_select_options(self._discovered_clients)
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004
    ) -> ArubaIAPOptionsFlow:
        """Return the options flow handler."""
        return ArubaIAPOptionsFlow()


class ArubaIAPOptionsFlow(config_entries.OptionsFlow):
    """Options flow — change host/credentials/tracking/polling after setup."""

    async def async_step_init(  # noqa: PLR0912
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options form."""
        errors: dict[str, str] = {}
        current = self.config_entry.data
        current_options = self.config_entry.options

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            scan_interval = user_input[CONF_SCAN_INTERVAL]
            cleanup_enabled = user_input[CONF_CLEANUP_ENABLED]
            cleanup_days = user_input[CONF_CLEANUP_DAYS]

            connection_changed = (
                host != current.get(CONF_HOST)
                or username != current.get(CONF_USERNAME)
                or password != current.get(CONF_PASSWORD)
            )

            if connection_changed:
                error_key, _ = await _test_connection(
                    self.hass, host, username, password
                )
                if error_key:
                    errors["base"] = error_key

            if not errors:
                # data holds connection fields only; options holds everything
                # runtime-changeable. Options here are written via async_update_entry
                # directly rather than via the return self.async_create_entry(...)
                # auto-options mechanism, so both dicts land in one call. Keeping
                # data scoped to connection fields (instead of also duplicating
                # scan_interval/cleanup into it, as before) avoids a
                # stale, unused copy of those settings sitting in entry.data.
                old_scan_interval = current_options.get(
                    CONF_SCAN_INTERVAL,
                    current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                )

                coordinator = self.config_entry.runtime_data
                live_devices = dict((coordinator.data or {}) if coordinator else {})
                known_macs = set(coordinator.last_seen if coordinator else {})
                known_macs.update(live_devices)

                registry = er.async_get(self.hass)
                for entity in er.async_entries_for_config_entry(
                    registry, self.config_entry.entry_id
                ):
                    if entity.domain != "device_tracker":
                        continue
                    known_macs.add(format_mac(entity.unique_id))

                old_tracked = current_options.get(
                    CONF_TRACKED_DEVICES,
                    current.get(CONF_TRACKED_DEVICES, sorted(known_macs)),
                )
                tracked_devices = sorted(
                    format_mac(mac) for mac in user_input.get(CONF_TRACKED_DEVICES, [])
                )

                data_update = {
                    CONF_HOST: host,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                }
                options_update = {
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_CLEANUP_ENABLED: cleanup_enabled,
                    CONF_CLEANUP_DAYS: cleanup_days,
                    CONF_TRACKED_DEVICES: tracked_devices,
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data_update,
                    options=options_update,
                )

                LOGGER.debug(
                    "Aruba Device Tracker options updated via options form: "
                    "scan_interval=%ds, cleanup_enabled=%s, "
                    "cleanup_days=%d",
                    scan_interval,
                    cleanup_enabled,
                    cleanup_days,
                )

                selection_changed = set(old_tracked) != set(tracked_devices)

                if selection_changed:
                    device_registry = dr.async_get(self.hass)
                    for mac in set(old_tracked) - set(tracked_devices):
                        normalised_mac = format_mac(mac)
                        sensor_prefix = f"{normalised_mac}_"
                        for entity in er.async_entries_for_config_entry(
                            registry, self.config_entry.entry_id
                        ):
                            if entity.unique_id == normalised_mac or (
                                entity.domain == "sensor"
                                and entity.unique_id.startswith(sensor_prefix)
                            ):
                                registry.async_remove(entity.entity_id)
                        device = device_registry.async_get_device(
                            identifiers={(DOMAIN, normalised_mac)}
                        )
                        if device:
                            device_registry.async_remove_device(device.id)

                if connection_changed or selection_changed:
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self.config_entry.entry_id
                        )
                    )
                elif scan_interval != old_scan_interval:
                    coordinator = self.config_entry.runtime_data
                    if coordinator is not None:
                        coordinator.update_interval = timedelta(seconds=scan_interval)

                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_USERNAME, default=current.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_options.get(
                            CONF_SCAN_INTERVAL,
                            current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        ),
                    ): vol.All(
                        int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    ),
                    vol.Optional(
                        CONF_CLEANUP_ENABLED,
                        default=current_options.get(
                            CONF_CLEANUP_ENABLED,
                            current.get(CONF_CLEANUP_ENABLED, DEFAULT_CLEANUP_ENABLED),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_CLEANUP_DAYS,
                        default=current_options.get(
                            CONF_CLEANUP_DAYS,
                            current.get(CONF_CLEANUP_DAYS, DEFAULT_CLEANUP_DAYS),
                        ),
                    ): vol.All(
                        int, vol.Range(min=MIN_CLEANUP_DAYS, max=MAX_CLEANUP_DAYS)
                    ),
                    vol.Optional(
                        CONF_TRACKED_DEVICES,
                        default=self._current_tracked_devices(),
                    ): _device_selector(self._current_device_options()),
                }
            ),
            errors=errors,
        )

    def _known_devices(self) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        """Return every known client and registry name for the options form."""
        coordinator = self.config_entry.runtime_data
        devices = dict((coordinator.data or {}) if coordinator else {})
        for mac in coordinator.last_seen if coordinator else {}:
            devices.setdefault(format_mac(mac), {})

        registry = er.async_get(self.hass)
        stored_names: dict[str, str] = {}
        for entity in er.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            if entity.domain != "device_tracker":
                continue
            mac = format_mac(entity.unique_id)
            devices.setdefault(mac, {})
            name = entity.name or entity.original_name
            if name:
                stored_names[mac] = name
        return devices, stored_names

    def _current_tracked_devices(self) -> list[str]:
        """Return explicit selection, preserving all clients for old entries."""
        devices, _ = self._known_devices()
        configured = self.config_entry.options.get(
            CONF_TRACKED_DEVICES,
            self.config_entry.data.get(CONF_TRACKED_DEVICES),
        )
        return sorted(configured if configured is not None else devices)

    def _current_device_options(self) -> list[SelectOptionDict]:
        """Return choices for the options form."""
        devices, stored_names = self._known_devices()
        for mac in self._current_tracked_devices():
            devices.setdefault(mac, {})
        return _device_select_options(devices, stored_names)
