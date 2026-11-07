"""Coordinator + MQTT backends for the EVDANCE charger.

Two backends:
  * local  - rides the Home Assistant MQTT broker (the charger must publish to
             it; see README DNS-redirect). No charger credentials needed.
  * cloud  - EXPERIMENTAL. Connects directly to the EVDANCE cloud broker with
             its own MQTT client, using credentials you supply. Untested against
             the live cloud (client-id / ACL behaviour unknown).
"""
from __future__ import annotations

import asyncio
import json
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_HOST,
    CONF_MODE,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SERIAL,
    CONF_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    MODE_CLOUD,
    MODE_LOCAL,
    base_topic,
    signal_update,
)

_LOGGER = logging.getLogger(__name__)


class EvdanceCoordinator:
    """Holds latest state; delegates transport to a backend."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.serial: str = entry.data[CONF_SERIAL]
        self.model: str = entry.data[CONF_MODEL]
        self.base: str = base_topic(self.model, self.serial)
        self.mode: str = entry.data.get(CONF_MODE, MODE_LOCAL)
        self.data: dict = {}
        self._backend = (
            _CloudBackend(self) if self.mode == MODE_CLOUD else _LocalBackend(self)
        )

    async def async_setup(self) -> None:
        await self._backend.async_start()

    async def async_unload(self) -> None:
        await self._backend.async_stop()

    @property
    def command_topic(self) -> str:
        return f"{self.base}/function/get"

    @property
    def state_topics(self) -> tuple[str, str]:
        return (f"{self.base}/property/post", f"{self.base}/event/post")

    @callback
    def ingest(self, payload) -> None:
        """Parse a status/event payload and notify entities."""
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            return
        if not isinstance(data, dict):
            return
        self.data.update(data)
        async_dispatcher_send(self.hass, signal_update(self.serial))

    async def async_set_current(self, amps: int) -> None:
        await self._backend.async_publish({"current": int(amps)})

    async def async_set_charging(self, charging: bool) -> None:
        await self._backend.async_publish({"on_off": 1 if charging else 2})


class _LocalBackend:
    """Uses the Home Assistant MQTT broker."""

    def __init__(self, coordinator: EvdanceCoordinator) -> None:
        self.c = coordinator
        self._unsubs: list = []

    async def async_start(self) -> None:
        for topic in self.c.state_topics:
            unsub = await mqtt.async_subscribe(self.c.hass, topic, self._on_message)
            self._unsubs.append(unsub)

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _on_message(self, msg) -> None:
        self.c.ingest(msg.payload)

    async def async_publish(self, payload: dict) -> None:
        await mqtt.async_publish(
            self.c.hass, self.c.command_topic, json.dumps(payload)
        )


class _CloudBackend:
    """EXPERIMENTAL: direct connection to the EVDANCE cloud broker."""

    def __init__(self, coordinator: EvdanceCoordinator) -> None:
        self.c = coordinator
        d = coordinator.entry.data
        self._host = d.get(CONF_HOST, DEFAULT_HOST)
        self._port = d.get(CONF_PORT, DEFAULT_PORT)
        self._username = d.get(CONF_USERNAME, DEFAULT_USERNAME)
        self._password = d.get(CONF_PASSWORD)
        self._task: asyncio.Task | None = None
        self._client = None
        self._stop = False

    async def async_start(self) -> None:
        self._stop = False
        self._task = self.c.hass.async_create_background_task(
            self._run(), name=f"evdance-cloud-{self.c.serial}"
        )

    async def async_stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        import aiomqtt

        while not self._stop:
            try:
                async with aiomqtt.Client(
                    hostname=self._host,
                    port=self._port,
                    username=self._username,
                    password=self._password,
                    identifier=f"ha-evdance-{self.c.serial}",
                ) as client:
                    self._client = client
                    for topic in self.c.state_topics:
                        await client.subscribe(topic)
                    _LOGGER.info("EVDANCE cloud connected for %s", self.c.serial)
                    async for message in client.messages:
                        self.c.ingest(message.payload)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self._client = None
                if self._stop:
                    break
                _LOGGER.warning(
                    "EVDANCE cloud connection error (%s); retrying in 15s", err
                )
                await asyncio.sleep(15)
        self._client = None

    async def async_publish(self, payload: dict) -> None:
        if self._client is None:
            _LOGGER.warning("EVDANCE cloud not connected; command dropped")
            return
        await self._client.publish(self.c.command_topic, json.dumps(payload))
