#!/usr/bin/env python3
"""Capture an EVDANCE charger's MQTT credentials automatically.

The charger signs in to its broker with username `yccsmart` and a per-device
password. To let it connect to your own Mosquitto you need that password - but
it's only revealed in the charger's MQTT CONNECT. This helper stands up a
throwaway listener on port 1883, lets the charger connect once, and prints the
client-id / username / password from the CONNECT. No packet capture, no gateway
access, no cloud login.

Usage:
  1. Pick a host the charger can reach with nothing else on port 1883
     (stop Mosquitto briefly, or use a spare machine).
  2. Point `mqtt.evdances.com` at THIS host's IP in your local DNS
     (UniFi / Pi-hole / etc.).
  3. sudo python3 scripts/capture_credentials.py       # 1883 is privileged
  4. Reboot the charger (breaker, or unplug ~10s).
  5. It prints the credentials and exits. Put them in your Mosquitto `logins:`,
     then repoint DNS at your real broker and reboot the charger again.

Captures your own device's credentials on your own network - nothing leaves it.
"""
from __future__ import annotations

import asyncio


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    mult, val = 1, 0
    while True:
        b = data[i]
        i += 1
        val += (b & 0x7F) * mult
        if not b & 0x80:
            return val, i
        mult *= 128


def _read_str(data: bytes, i: int) -> tuple[bytes, int]:
    ln = (data[i] << 8) | data[i + 1]
    i += 2
    return data[i : i + ln], i + ln


def parse_connect(data: bytes):
    """Return (level, client_id, username, password) or None if incomplete."""
    if not data or data[0] >> 4 != 1:  # not a CONNECT
        return None
    i = 1
    _rem, i = _read_varint(data, i)
    _name, i = _read_str(data, i)          # protocol name "MQTT"
    level = data[i]; i += 1
    flags = data[i]; i += 1
    i += 2                                  # keepalive
    if level >= 5:                          # MQTT v5 CONNECT properties
        plen, i = _read_varint(data, i)
        i += plen
    _client_id, i = _read_str(data, i)
    client_id = _client_id
    if flags & 0x04:                        # will present
        if level >= 5:
            wplen, i = _read_varint(data, i); i += wplen
        _wt, i = _read_str(data, i)
        _wp, i = _read_str(data, i)
    username = password = b""
    if flags & 0x80:
        username, i = _read_str(data, i)
    if flags & 0x40:
        password, i = _read_str(data, i)
    return (
        level,
        client_id.decode(errors="replace"),
        username.decode(errors="replace"),
        password.decode(errors="replace"),
    )


async def main() -> None:
    done = asyncio.Event()

    async def handle(reader, writer) -> None:
        data = b""
        try:
            while len(data) < 4096:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=20)
                if not chunk:
                    break
                data += chunk
                try:
                    parsed = parse_connect(data)
                except (IndexError, ValueError):
                    continue                 # need more bytes
                if parsed:
                    level, cid, user, pw = parsed
                    print("\n=== EVDANCE charger connected ===")
                    print(f"  MQTT version : {level}")
                    print(f"  Client ID    : {cid}")
                    print(f"  Username     : {user}")
                    print(f"  Password     : {pw}")
                    print("\nAdd to the Mosquitto add-on config:")
                    print("  logins:")
                    print(f"    - username: {user}")
                    print(f"      password: {pw}\n")
                    # CONNACK (success) so the charger doesn't hammer-reconnect
                    writer.write(
                        bytes([0x20, 0x03, 0x00, 0x00, 0x00])
                        if level >= 5
                        else bytes([0x20, 0x02, 0x00, 0x00])
                    )
                    await writer.drain()
                    done.set()
                    break
        except asyncio.TimeoutError:
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "0.0.0.0", 1883)
    print("Listening on 0.0.0.0:1883 - point the charger here and reboot it.")
    print("Waiting for the charger's CONNECT...  (Ctrl-C to stop)")
    async with server:
        await done.wait()
    print("Captured. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
