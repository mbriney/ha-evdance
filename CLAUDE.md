# CLAUDE.md — ha-evdance

Guidance for a future Claude session picking up this repo for an upgrade or bugfix,
so you don't have to rediscover the protocol. Keep this file current when behavior changes.

## What this is
A Home Assistant (HACS) custom integration for **EVDANCE** Level 2 EV chargers
(model family `ACT4002UA2`, built on the `ycc` ODM platform; rebadges likely share it).
It gives native HA monitoring + control over MQTT, with no cloud dependency in the
default (local) mode.

Domain: `evdance`. Author/codeowner: `@mbriney`.

## The charger protocol (reverse-engineered Nov 2026)
The charger is an ESP32 that talks **plaintext MQTT v5 on port 1883** to the vendor
cloud `mqtt.evdances.com` (→ Tencent Cloud). JSON payloads, no app-layer encryption.
It authenticates with client-id = its serial, username `yccsmart`, and a per-device
password (sent in the MQTT CONNECT). NOT Tuya, NOT OCPP.

Base topic: `ycc/<model>/<serial>`  (e.g. `ycc/ACT4002UA2/ACT4002UA22603P10028`)

- `…/property/post`  (device→broker, every ~5-10s) — status:
  `{"voltage":245,"current":34,"status":3,"temper":33,"kw":8330,"kwh":20,"mtp":1,"hour":0,"minute":2,"setcurrent":40,"setKwh":0}`
- `…/event/post`     (device→broker) — plug-in / charge start+stop; adds `chargingType`, `chargingId`
- `…/info/post`      (device→broker) — firmware/serial at boot
- `…/function/get`   (broker→device) — **commands** (this is the control channel)
- `…/ntp/post` → cloud replies `…/ntp/get` `{"gmtOffset":0,"seconds":<epoch>}`
- `…/ota/get`, `…/moduleOta/get` — OTA (leave to the cloud bridge)

Field meanings / status codes:
- `status`: 1 = idle, 2 = connected/plugged, 3 = charging
- `kw` = **watts** (not kW). `kwh` = session energy, behaves like **Wh** (VERIFY against a known full session).
- `current` live amps, `voltage` V, `temper` °C, `setcurrent` = configured max amps (the app slider),
  `setKwh` target energy limit (0 = none), `hour`/`minute` elapsed charge time, `mtp` unknown (always 1).

Commands (publish to `…/function/get`):
- set amps:  `{"current":32}`
- start:     `{"on_off":1}`
- stop:      `{"on_off":2}`

All verified live (slider change, start, stop all took effect).

## How the integration connects
Two backends behind one coordinator (`coordinator.py`), chosen by config-entry `mode`:
- **local** (default): rides the HA MQTT broker. The charger must publish to that broker —
  user does a DNS override (`mqtt.evdances.com` → their broker IP) + reboots the charger.
  Config flow auto-discovers the charger by listening on `ycc/+/+/property/post`.
- **cloud** (experimental, UNTESTED against the live broker): the integration opens its own
  `aiomqtt` client straight to `mqtt.evdances.com` with user-supplied credentials. Unknowns:
  whether the cloud broker accepts a foreign client-id and lets a non-device client sub/pub the
  device topics.

Entities (all in their own platform files, driven by the coordinator's `data` dict + a dispatcher signal):
- sensors: power(W), current(A), voltage(V), session energy(kWh from Wh/1000), temperature(°C), status(enum)
- number: set current (6-40A slider) → publishes `{"current":N}`
- switch: charging on/off → publishes `{"on_off":1|2}`; is_on when status==3

## Setup the user must do (local mode)
1. Mosquitto broker reachable by the charger. The **HA Mosquitto add-on has no anonymous mode**,
   so add a `logins:` entry: username `yccsmart` + the charger's per-device password.
   (Get the password with `scripts/capture_credentials.py`, or from a `tcpdump -A ... tcp port 1883`.)
2. Local DNS override: `mqtt.evdances.com` → broker IP (router / Pi-hole / UniFi; NOT something the
   integration can do — it's the irreducible manual step).
3. Reboot the charger. Optional: bridge the local Mosquitto up to `49.51.243.232:1883` (by IP, to avoid
   a DNS loop) with `remote_clientid=<serial>`, `remote_username=yccsmart`, remote password, so the
   EVDANCE app + OTA keep working.

## Credentials
The device MQTT password is a per-device secret. **Never commit it.** It lives in the user's Vaultwarden.
The repo needs no secrets.

## Helper scripts (no cloud login needed)
- `scripts/discover.py` — connect to the broker, print chargers + live state (paho-mqtt).
- `scripts/capture_credentials.py` — throwaway 1883 listener that prints the charger's MQTT
  CONNECT (client-id/user/pass). Point the charger at it briefly (DNS), reboot, read creds.

## HACS submission / release playbook (learned the hard way)
- **Brand icon MUST be at `custom_components/evdance/brand/icon.png`** (inside the integration dir,
  NOT repo root). The HACS brands check looks there first, then falls back to home-assistant/brands.
  (brands repo is closed to new custom integrations as of 2026, so ship in-repo.)
- `.github/workflows/validate.yml` runs `hacs/action@main` (category: integration) + `home-assistant/actions/hassfest@master`.
  Both must be green with **no `ignore`**. The HACS action also checks **repo topics** — the repo
  must have topics set, or the `topics` check fails.
- `manifest.json` key order must satisfy hassfest: `domain`, `name`, then the rest alphabetically.
  `version` must match the release tag.
- A full GitHub **release** is required for the hacs/default catalog (a tag alone is not enough).
- To be added to the Marketplace: fork `hacs/default`, branch off `master`, add `mbriney/ha-evdance`
  to the `integration` JSON list alphabetically, open the PR from a personal account, do NOT request
  reviews (that auto-closes it). Review takes months.
- Gotcha for agents: the Cowork sandbox git proxy blocks **repo-settings writes** (description/topics)
  via API/`gh` — set those through the GitHub web UI (signed-in browser) or have the owner do it.

## Full protocol + capture history
See the user's Outline runbook: **Homelab / "EVDANCE EV Charger — Local Control via MQTT"**.

## Open items / roadmap
- Verify `kwh` units (Wh vs 0.01 kWh) against a known full charge.
- Test cloud mode against the live broker; confirm whether the password is static or rotating.
- Reverse the EVDANCE account **HTTP API** (login → device list → credentials) to enable a true
  turnkey cloud setup (enter email+password, no DNS/broker). The app's HTTP didn't appear in an
  mitmproxy run because the app was already logged in (MQTT-only resume); force it by logging out/in
  while capturing (watch for cert pinning).
- Optional `brand/logo.png` (the official wordmark is white text — handle light/dark).
