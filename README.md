# ZTE MC888A Ultra Presence for Home Assistant

![ZTE MC888A Ultra Presence icon](custom_components/zte_mc888a_presence/brand/icon.png)

Local presence tracking for ZTE MC888A Ultra routers using their HTTPS **Goform** API. Initially developed and tested against firmware `BD_ATMC888AULTRAV1.0.0B20` using the router's password-only `LOGIN` endpoint.

> **Status: v0.1.4 / active testing.** The integration has been confirmed to work in Home Assistant with the ZTE MC888A Ultra on the stated firmware.

## Features

- Local HTTPS communication; no ZTE cloud account or GPS tracking
- Log in with `LOGIN`, SHA256(SHA256(password) + LD) as established by manual router testing
- Reuse one cookie session; reauthenticate on a clearly stale Wi-Fi client list
- Poll Wi-Fi (`station_list`) and Ethernet (`lan_station_list`) once per minute
- Create native device trackers **only** for explicitly configured MAC addresses
- Configurable away delay (default 300 seconds); present immediately on detection
- On router communication errors, entities become unavailable instead of marking everyone away
- Diagnostic Wi-Fi, LAN and total client counts, and last successful poll time
- English/German UI; local credentials stored in HA config entries, never committed to source

## Integration icon

The custom logo is bundled as `custom_components/zte_mc888a_presence/brand/icon.png` (transparent 256×256 PNG). Home Assistant 2026.3+ displays it automatically on the integration page. After updating, restart Home Assistant and refresh its frontend. The HACS repository listing may still display **icon not available** due to a separate HACS frontend issue; the Home Assistant integration page should use the bundled icon.

## Installation

This repo is public so Home Assistant **Marketplace** (Home Assistant 2026.11+) can install it as a *custom repository*.

1. In **Settings → Marketplace**, add the repository URL as a custom integration repository:
   `https://github.com/andreassamitsch/ha-zte-mc888a-presence`
2. Install **ZTE MC888A Ultra Presence**, then restart Home Assistant.
3. In **Settings → Devices & services → Add integration**, select **ZTE MC888A Ultra Presence**.
4. Enter the router IP (normally `192.168.1.1`) and the local **router web password**. This firmware needs **no username**.
5. Open the integration's **Configure** dialog and enter tracked clients:
   `AA:BB:CC:DD:EE:FF=Andi S23, 11:22:33:44:55:66=Iris iPhone`
6. Save; the integration reloads and creates the selected `device_tracker` entities. Link them to persons only after verifying their states.

For manual installation, copy `custom_components/zte_mc888a_presence` to Home Assistant's `config/custom_components/` folder and restart Home Assistant.

### First installation

This integration is still under active development. Before using the trackers to control heating, check the router login, sensor counts, and delayed presence states in Home Assistant.

## Router session expiry and zero-client safeguards

Starting in **0.1.2**, a zero/blank Wi-Fi list is **never accepted as a valid
absence scan**. This fixes a case where the MC888A Ultra temporarily returned
`station_list: []` or `station_list: ""` and `wifi_access_sta_num: 0`
after a session expired, falsely reporting all household devices as away.
The integration attempts one fresh login with a new cookie jar, limiting
retries to once every five minutes. If the list is still empty, the
coordinator becomes unavailable; presence automations must not treat
`unavailable` as `not_home`.

**Limitation:** This safeguard deliberately assumes at least one WLAN client is
normally connected. Networks that legitimately reach zero Wi-Fi clients are
not currently supported without changing this behavior.

## Removing old phones and device trackers

1. Open **Settings → Devices & services → ZTE MC888A Ultra Presence → Configure**.
2. Under **Tracked devices**, remove the obsolete MAC address or device entry (not just the display name). Leave the MACs for devices you still want to track.
3. Save. The integration reloads and (from **v0.1.3**) removes the retired device and its entity-registry entry automatically. The router and active phone trackers are never removed.
4. A **Delete** action is also supported in Home Assistant for a device that has already been removed from the configuration. Active configured devices cannot be deleted until their MAC is removed from the options.

If several device entries share a friendly name (for example, "Andi S23"), use each device's MAC address to determine which one to keep. Deleting a device removes its Home Assistant entity registration and may break person associations, dashboard cards, and automations referencing it.

## Reliable presence

- Samsung Galaxy S23: randomized Wi-Fi MAC is normally persistent for the same saved network; record the MAC displayed by the router while the phone is connected.
- iPhone: set **Private Wi-Fi Address → Fixed** for this home network; rotating MAC will break MAC-based identification.
- The router may temporarily omit clients when their Wi-Fi radio is sleeping. Default away hysteresis is 5 minutes, but longer might be useful for iPhones.
- A communication failure makes trackers **unavailable**. Do not use `not home` to mean both `not_home` and `unavailable`; use explicit state comparisons.
- Router login may invalidate another administrative login. This integration tries to reuse its existing session.

## Security

The ZTE router in scope presents an untrusted HTTPS certificate. This integration intentionally disables certificate verification **for the LAN router connection only**; the traffic remains encrypted but the router is **not authenticated against an external CA**. Run this only on a trusted home network. No remote management, UPnP port forwarding or cloud service is needed. The password remains inside Home Assistant storage; device MACs and credentials must not be committed to GitHub.

## Compatibility

Only password-based `LOGIN` has been implemented. Some ZTE routers use `LOGIN_MULTI_USER` or different Goform fields; those are not currently supported. Not affiliated with ZTE or Home Assistant.

## Development

```sh
python3 -m compileall -q custom_components/zte_mc888a_presence
python3 -m unittest discover -s tests -v
```

Open issues with the firmware version, sanitized responses and error logs **without credentials, cookies or public IP addresses**.
