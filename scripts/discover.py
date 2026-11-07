#!/usr/bin/env python3
"""Discover EVDANCE chargers on your MQTT broker and print their live state.

No cloud login and no packet capture needed. Once your charger is pointed at
this broker (see the README's DNS-redirect step), run:

    pip install paho-mqtt
    python3 scripts/discover.py --host 192.168.1.12

It subscribes to ycc/# and prints each charger's model, serial, and status as
it reports in. Use the serial it prints when adding the integration (or just
let the integration auto-discover it).
"""
from __future__ import annotations

import argparse
import json

import paho.mqtt.client as mqtt


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover EVDANCE chargers via MQTT")
    parser.add_argument("--host", required=True, help="MQTT broker host or IP")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--username", help="Broker username (if required)")
    parser.add_argument("--password", help="Broker password (if required)")
    args = parser.parse_args()

    seen: set[str] = set()

    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"Connected (rc={rc}). Listening on ycc/#  —  Ctrl-C to stop.\n")
        client.subscribe("ycc/#")

    def on_message(client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) < 3 or parts[0] != "ycc":
            return
        model, serial = parts[1], parts[2]
        try:
            data = json.loads(msg.payload)
        except (ValueError, TypeError):
            data = {}
        if serial not in seen:
            seen.add(serial)
            print(f"Found charger: model={model}  serial={serial}")
        if isinstance(data, dict) and "status" in data:
            print(
                f"  {serial}: status={data.get('status')} "
                f"current={data.get('current')}A power={data.get('kw')}W "
                f"set={data.get('setcurrent')}A"
            )

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, 60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nDiscovered serials:", ", ".join(sorted(seen)) or "(none)")


if __name__ == "__main__":
    main()
