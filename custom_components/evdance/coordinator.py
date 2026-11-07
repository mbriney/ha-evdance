"""MQTT bridge between Home Assistant and an EVDANCE charger.

The charger speaks plaintext MQTT (JSON) to its cloud broker. Point it at the
same broker Home Assistant uses (see README: DNS redirect) and this coordinator
subscribes to its status topics and publishes commands.
"""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_MODEL, CONF_SERIAL, base_topic, signal_update

_LOGGER = logging.getLogger(__name__)


class EvdanceCoordinator:
    """Holds the latest state and talks to the charger over MQTT."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.serial: str = entry.data[CONF_SERIAL]
        self.model: str = entry.data[CONF_MODEL]
        self.base: str = base_topic(self.model, self.serial)
        self.data: dict = {}
        self._unsubs: list = []

    async def async_setup(self) -> None:
        """Subscribe to the charger's status + event topics."""
        for suffix in ("property/post", "event/post"):
            unsub = await mqtt.async_subscribe(
                self.hass, f"{self.base}/{suffix}", self._message_received
            )
            self._unsubs.append(unsub)

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _message_received(self, msg) -> None:
        try:
            payload = json.loads(msg.payload)
        except (ValueError, TypeError):
            _LOGGER.debug("Ignoring non-JSON payload on %s", msg.topic)
            return
        if not isinstance(payload, dict):
            return
        self.data.update(payload)
        async_dispatcher_send(self.hass, signal_update(self.serial))

    async def async_set_current(self, amps: int) -> None:
        """Set the max charging current (amps)."""
        await self._publish({"current": int(amps)})

    async def async_set_charging(self, charging: bool) -> None:
        """Start (True) or stop (False) charging."""
        await self._publish({"on_off": 1 if charging else 2})

    async def _publish(self, payload: dict) -> None:
        await mqtt.async_publish(
            self.hass, f"{self.base}/function/get", json.dumps(payload)
        )
