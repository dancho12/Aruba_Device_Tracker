# Aruba Instant AP — Home Assistant Integration

A custom integration for Home Assistant that tracks devices connected to an Aruba Instant AP using the local REST API.

> **Disclaimer:** This is an unofficial integration and is not affiliated with or endorsed by Aruba Networks. Use at your own risk.

## Fork Notice

This repository is a personal-use fork of [Jam3s97/Aruba_Device_Tracker](https://github.com/Jam3s97/Aruba_Device_Tracker). Credit for the original integration and its foundation belongs to the upstream author and contributors.

The changes in this fork were developed by [dancho12](https://github.com/dancho12) with assistance from [OpenAI Codex](https://openai.com/codex/).

This fork is maintained primarily for personal use. Updates, compatibility fixes, support, and continued maintenance are not guaranteed. If you need the upstream behavior or broader community support, use the original repository.

## Features

- **Device Tracker** — marks devices home/away based on Wi-Fi association
- **Extra attributes per device:**
  - `MAC` — Client MAC address
  - `Host name` — Client hostname
  - `access_point` — which AP the device is connected to
  - `essid` — the SSID/network name
  - `ip_address` — current IP address
  - `os` — operating system detected by the IAP
  - `channel` — Wi-Fi channel
  - `client_type` — client radio/type reported by Aruba (for example `a-HE`)
  - `role` — Aruba user role assigned to the client
  - `ipv6_address` — global IPv6 address, when available
  - `signal` — signal strength
  - `speed` — link speed
- **Config Flow** — set up entirely from the HA UI, no YAML required
- **Explicit device selection** — choose exactly which discovered clients are exposed to Home Assistant
- **Native device removal** — remove a tracked client from its Home Assistant device page without it being recreated on the next poll
- **Manual client refresh** — request an immediate IAP scan from the Aruba IAP device page
- **Optional client diagnostics** — ten per-client sensors are registered disabled by default and can be enabled individually
- **Configurable poll interval** — how often the IAP is queried (default 30s, range 10–300s)
- **Auto-remove stale devices** — automatically remove entities for devices not seen for a configurable number of days
- **Friendly name renaming** — rename any device via the HA entity registry
- **Offline devices stay away** — devices that are away when HA restarts correctly restore their away state; no unavailable flash or "entity no longer provided" warnings

## Requirements

- Aruba Instant AOS 8.5.0+
- Admin account on the IAP
- REST API enabled on the IAP:

```
Instant AP# configure
Instant AP(config)# allow-rest-api
Instant AP(config)# end
Instant AP# commit apply
```

## Installation

### HACS (recommended)
1. Add this repository as a custom repository in HACS
2. Search for **Aruba Device Tracker** and install
3. Restart Home Assistant

### Manual
1. Copy the `custom_components/aruba_device_tracker` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Aruba Device Tracker**
3. **Step 1 — Connection:**
   - **IP Address** — your IAP or Virtual Controller IP (e.g. `192.168.1.10`)
   - **Username** — IAP admin username
   - **Password** — IAP admin password
4. **Step 2 — Polling & Cleanup:**
   - **Poll interval** — how often the IAP is queried in seconds (default 30s)
   - **Auto-Remove Stale Devices** — automatically remove entities for devices not seen for a set number of days (default: on)
   - **Auto-Remove Stale Devices After** — number of days of inactivity before an entity is removed (default: 30 days)
5. **Step 3 — Devices:** select the Aruba clients that should have `device_tracker` entities. Unselected and newly discovered clients remain available in the integration options.

## Options

All settings and the tracked-device selection are editable after setup via **Configure** on the integration card, including IP address and credentials. Changing the IP or credentials will trigger a reconnection test before saving.

The poll interval, manual client refresh, and stale device cleanup settings are also available as entities on the IAP device card for quick changes without opening the options flow. After pressing **Refresh client list**, reopen **Configure** to select newly discovered clients.

## Selecting and Removing Devices

Only clients selected under **Settings → Devices & Services → Aruba Device Tracker → Configure** are exposed as `device_tracker` entities. Clear a selection to remove its entity and device; select it again later to restore it.

Each tracked client is also represented as a native Home Assistant device. The **Delete** action on that device's page removes it from the selected list, so the integration does not recreate it on the next poll. Home Assistant intentionally keeps the delete button disabled on the entity-edit dialog while an integration provides that entity; use the device page or the integration selection instead.

Each selected client also has disabled-by-default diagnostic sensors for IP, IPv6, operating system, Wi-Fi network, access point, channel, client type, role, signal, and link speed. Enable only the sensors you need from the client's device page.

## Renaming Devices

Go to **Settings → Devices & Services → Entities**, find the device tracker entity, click it, then click the pencil icon to give it a friendly name. This is stored in the HA entity registry and persists across restarts.

## Auto-Remove Stale Devices

When enabled, device tracker entities that have not been seen for the configured number of days are automatically removed after each poll cycle. The last-seen timestamp for each device is stored persistently and survives HA restarts.

- **Auto-Remove Stale Devices** switch — enable or disable the feature
- **Auto-Remove Stale Devices After** number — days threshold (1–365, default 30)

Both are configurable during setup, via the options flow, or directly on the IAP device card.

> [!NOTE]
> Auto-remove defaults to **on** with a 30-day threshold. Devices are only removed if they haven't appeared in any poll result for the full threshold period. If a device reconnects, its last-seen timestamp resets and the countdown starts again.

## Default Away Timer Behaviour

The default Aruba IAP client inactivity timer is 1000 seconds (~16 minutes). When a client disconnects, its session remains in the client table until the timer expires.

- **Time to show away:** inactivity timeout + time until next poll
- **Time to show home:** time until next poll after the client reconnects (under 30 seconds by default)

You may want to reduce the inactivity timer. For example, to 300 seconds (5 minutes):

> [!NOTE]
> Consider the impact of lowering this value in your environment. The inactivity timeout controls how long a client session remains active after disconnecting. Values below 300 seconds may cause re-authentication events on some devices.

**Via Web GUI:**
1. Navigate to **Configuration → Networks**, select your network and click **Edit** (pencil icon)
2. Click **Show Advanced**
3. Under **Miscellaneous**, update **Inactivity timeout** to the desired value
<img width="1084" height="295" alt="Inactivity timeout setting" src="https://github.com/user-attachments/assets/a0dac1a7-bd69-4b8b-b3bf-f9cb838e3035" />
4. Click **Next → Next → Next → Finish**

**Via CLI:**
```
Instant AP# configure
Instant AP (config) # wlan ssid-profile <name>
Instant AP (SSID Profile "<name>") # inactivity-timeout 300    (60–86400 seconds)
Instant AP (SSID Profile "<name>") # end
Instant AP# commit apply
```
