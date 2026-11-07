# ha-evdance

Control your EVDANCE Level 2 EV charger from Home Assistant.

A HACS custom integration for EVDANCE Wi-Fi chargers (model family `ACT4002UA2`
and other rebadges on the same `ycc` platform). Gives you native Home Assistant
**monitoring** (power, current, voltage, session energy, temperature, status)
and **control** (set charging current, start/stop) — locally, over MQTT.

> Status: early (0.1.0). Working protocol, functional entities. See Roadmap.

## How it works

EVDANCE chargers don't use Tuya, OCPP, or any documented local API. They hold a
persistent **plaintext MQTT** connection to the vendor cloud
(`mqtt.evdances.com`, Tencent Cloud) and exchange JSON. This integration doesn't
touch the cloud — instead you point the charger at **your own MQTT broker** (the
one Home Assistant already uses), and the integration subscribes to the
charger's status topics and publishes commands.

```
Charger  ──MQTT(1883)──►  your broker (Mosquitto)  ◄──►  Home Assistant
                                  │
                                  └──(optional bridge)──►  mqtt.evdances.com
                                      so the EVDANCE app keeps working
```

## Prerequisites

1. **An MQTT broker** that Home Assistant uses (e.g. the Mosquitto add-on), and
   the HA **MQTT integration** configured.
2. **Point the charger at your broker.** The charger resolves
   `mqtt.evdances.com` at boot, so add a local DNS override so that name
   resolves to your broker's IP:
   - UniFi / pfSense / AdGuard / Pi-hole: add an A record
     `mqtt.evdances.com → <your-broker-IP>`.
   - Your broker must accept the charger's connection. Simplest on a trusted
     LAN: `allow_anonymous true`. (The charger logs in with client-id = its
     serial, username `yccsmart`, and a per-device password.)
   - Reboot the charger (breaker or unplug 10s) so it reconnects to your broker.
3. *(Optional)* **Keep the EVDANCE app working** by bridging your broker up to
   the real cloud. In `mosquitto.conf`:
   ```conf
   connection evdance-cloud
   address 49.51.243.232:1883       # the real broker, by IP (avoids a DNS loop)
   bridge_protocol_version mqttv50
   remote_clientid <charger-serial>
   remote_username yccsmart
   remote_password <per-device-password>
   topic # both 0 "" ""
   ```
   Without the bridge, HA control still works fully; only the phone app and
   cloud OTA stop. (If you skip the bridge, add an HA automation to answer the
   charger's `ycc/<model>/<serial>/ntp/get` so its clock stays set.)

## Install

### Via HACS (custom repository)
1. HACS → ⋮ → **Custom repositories** → add `https://github.com/mbriney/ha-evdance`, category **Integration**.
2. Install **EVDANCE EV Charger**, then restart Home Assistant.

### Manual
Copy `custom_components/evdance/` into your HA `config/custom_components/` and restart.

## Configure

Settings → Devices & Services → **Add Integration** → *EVDANCE EV Charger*.

The integration **listens on your broker for a few seconds and auto-discovers**
any charger already reporting — just pick it from the list. Nothing to type, no
credentials, no packet capture. (If none is heard yet, you can enter the serial
by hand; it's on the unit and in the app under *About Charger*.)

### Helper: see what's on your broker
Not sure the charger is reporting yet? Run the bundled script:

```bash
pip install paho-mqtt
python3 scripts/discover.py --host <your-broker-IP>
```
It prints each charger's model, serial, and live status as it arrives.

## Entities

| Entity | Type | Notes |
|---|---|---|
| Power | sensor | watts |
| Current | sensor | amps (live draw) |
| Voltage | sensor | volts |
| Session energy | sensor | kWh (firmware reports Wh) |
| Temperature | sensor | °C |
| Status | sensor | idle / connected / charging |
| Set current | number | 6–40 A slider |
| Charging | switch | start / stop |

## Protocol (reference)

Base topic: `ycc/<model>/<serial>` (e.g. `ycc/ACT4002UA2/ACT4002UA2…`).

- Status (device → broker): `…/property/post`
  `{"voltage":245,"current":34,"status":3,"temper":33,"kw":8330,"kwh":20,"setcurrent":40,"setKwh":0,"hour":0,"minute":2}`
  `status`: 1 idle · 2 connected · 3 charging. `kw` = watts, `kwh` = Wh.
- Events (device → broker): `…/event/post` (plug-in, charge start/stop).
- Commands (broker → device): `…/function/get`
  - set amps: `{"current":32}`
  - start: `{"on_off":1}`  · stop: `{"on_off":2}`

## Credentials & the "easy install" question

For this **local** integration you need **no secrets** — only the serial, which
is auto-discovered. The per-device cloud password matters only for the optional
cloud *bridge*, and it's read straight off the charger's MQTT CONNECT the first
time it connects to your broker (watch the broker log, or `scripts/discover.py`).

## Roadmap

- Optional **cloud mode**: a login helper that pulls your charger list and
  credentials from the EVDANCE account API, for people who can't do the DNS
  redirect. (Needs the app's HTTP API reverse-engineered first.)
- Figure out whether the per-device password is static or derivable from the
  serial — if derivable, cloud mode needs no login at all.
- `setKwh` target-energy control; schedule (`hour`/`minute`) support.
- HACS default-repo submission once stable.

## Credits

Protocol reverse-engineered from on-network MQTT capture. Not affiliated with
EVDANCE.
