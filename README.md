# ZTE MC888A Presence for Home Assistant

Local presence tracking for ZTE MC888A Ultra routers using their HTTPS **Goform** API. Initially developed and tested against firmware `BD_ATMC888AULTRAV1.0.0B20` using the router's password-only `LOGIN` endpoint.

> **Status: v0.1.0 / early test build.** The CLI login and JSON device lists were confirmed on this firmware. The new Home Assistant integration code **has not yet been tested against the router in Home Assistant**.

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

## Installation

This repo is public so Home Assistant **Marketplace** (Home Assistant 2026.11+) can install it as a *custom repository*.

1. In **Settings → Marketplace**, add the repository URL as a custom integration repository:
   `https://github.com/andreassamitsch/ha-zte-mc888a-presence`
2. Install **ZTE MC888A Presence**, then restart Home Assistant.
3. In **Settings → Devices & services → Add integration**, select **ZTE MC888A Presence**.
4. Enter the router IP (normally `192.168.1.1`) and the local **router web password**. This firmware needs **no username**.
5. Open the integration's **Configure** dialog and enter tracked clients:
   `AA:BB:CC:DD:EE:FF=Andi S23, 11:22:33:44:55:66=Iris iPhone`
6. Save; the integration reloads and creates the selected `device_tracker` entities. Link them to persons only after verifying their states.

For manual installation, copy `custom_components/zte_mc888a_presence` to Home Assistant's `config/custom_components/` folder and restart Home Assistant.

### Important: this repository currently has a development branch

The code will be reviewed through a pull request before appearing on `main`. Do not install from `main` until that pull request has been merged.

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
