"""Config flow for EVDANCE — choose Local (default) or Cloud.

Local  : zero-touch. Listens on your HA MQTT broker and auto-discovers any
         charger already reporting. No credentials, no capture.
Cloud  : experimental. Connects straight to the EVDANCE cloud broker using
         credentials you supply.
"""
from __future__ import annotations

import asyncio

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_HOST,
    CONF_MODE,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SERIAL,
    CONF_USERNAME,
    DEFAULT_HOST,
    DEFAULT_MODEL,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    MODE_CLOUD,
    MODE_LOCAL,
)

DISCOVERY_TOPIC = "ycc/+/+/property/post"
DISCOVERY_SECONDS = 6


class EvdanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EVDANCE."""

    VERSION = 1

    def __init__(self) -> None:
        self._found: dict[str, str] = {}  # serial -> model

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        # Local listed first = the default choice.
        return self.async_show_menu(
            step_id="user", menu_options=[MODE_LOCAL, MODE_CLOUD]
        )

    # ---- Local -----------------------------------------------------------
    async def async_step_local(self, user_input=None) -> ConfigFlowResult:
        if not await _mqtt_available(self.hass):
            return self.async_abort(reason="mqtt_required")
        await self._discover()
        if self._found:
            return await self.async_step_pick()
        return await self.async_step_manual()

    async def _discover(self) -> None:
        found: dict[str, str] = {}

        @callback
        def _on_message(msg) -> None:
            parts = msg.topic.split("/")
            if len(parts) >= 4 and parts[0] == "ycc":
                found[parts[2]] = parts[1]  # serial -> model

        unsub = await mqtt.async_subscribe(self.hass, DISCOVERY_TOPIC, _on_message)
        try:
            await asyncio.sleep(DISCOVERY_SECONDS)
        finally:
            unsub()
        self._found = found

    async def async_step_pick(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            serial = user_input[CONF_SERIAL]
            if serial == "__manual__":
                return await self.async_step_manual()
            return await self._create_local(
                serial, self._found.get(serial, DEFAULT_MODEL)
            )

        options = {s: f"{m} ({s})" for s, m in self._found.items()}
        options["__manual__"] = "Enter manually…"
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({vol.Required(CONF_SERIAL): vol.In(options)}),
        )

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create_local(
                user_input[CONF_SERIAL].strip(), user_input[CONF_MODEL].strip()
            )
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL): str,
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
                }
            ),
        )

    async def _create_local(self, serial: str, model: str) -> ConfigFlowResult:
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"EVDANCE {serial}",
            data={CONF_MODE: MODE_LOCAL, CONF_SERIAL: serial, CONF_MODEL: model},
        )

    # ---- Cloud (experimental) -------------------------------------------
    async def async_step_cloud(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            serial = user_input[CONF_SERIAL].strip()
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"EVDANCE {serial} (cloud)",
                data={
                    CONF_MODE: MODE_CLOUD,
                    CONF_SERIAL: serial,
                    CONF_MODEL: user_input[CONF_MODEL].strip(),
                    CONF_HOST: user_input[CONF_HOST].strip(),
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL): str,
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): str,
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )


async def _mqtt_available(hass) -> bool:
    try:
        return await mqtt.async_wait_for_mqtt_client(hass)
    except Exception:  # noqa: BLE001
        return False
